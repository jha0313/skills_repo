#!/usr/bin/env python3
"""에이전트 스킬 폴더(SKILL.md)를 훑어 문제를 보고한다. 파일은 고치지 않고 세션 기록은 읽지 않는다.

사용:
  skills_lint.py                        # 이 컴퓨터에 설치된 스킬 폴더
  skills_lint.py --root <폴더> [--root …]  # 저장소 하나(아래 폴더까지 찾음). CI용
  옵션: --json, --fail-on error|warning|never (기본 error), --allow-name <이름> (이름 글자 규칙만 예외)

설치된 폴더: ~/.claude/skills, ~/.agents/skills, ~/.codex/skills, ./.claude/skills, ./.agents/skills.
규격 검사(이름·설명 길이·필드)는 https://agentskills.io/specification 기준(2026-11-24 확인).
종료 코드: 0 문제 없음, 1 --fail-on 수준 이상의 문제 있음, 2 실행 못 함(폴더 없음, 스킬 없음).
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import unquote

INSTALLED = ["~/.claude/skills", "~/.agents/skills", "~/.codex/skills", ".claude/skills", ".agents/skills"]
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
TEXT_FIELDS = {"name", "description", "license", "compatibility", "when_to_use"}
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_LIMIT, DESC_LIMIT, COMPAT_LIMIT = 64, 1024, 500
MAX_DEPTH = 5
SKIP_DIRS = {"node_modules", "__pycache__", "venv", "tests", "test", "fixtures", "evals"}
AGENT_DIRS = {".claude", ".agents", ".codex", ".cursor"}
SAMPLE_USERS = {"you", "user", "username", "name", "yourname", "me", "runner"}


# ---- 스킬 찾기 ----

def scan_dirs(path):
    try:
        with os.scandir(path) as it:
            return sorted((e for e in it), key=lambda e: e.name)
    except OSError:
        return []


def find_installed(root):
    """에이전트가 읽는 모양대로 한 단계만 본다. 링크는 따라간다."""
    found, dangling = [], []
    for e in scan_dirs(root):
        if e.is_symlink() and not os.path.exists(e.path):
            dangling.append(e.path)
        elif os.path.isfile(os.path.join(e.path, "SKILL.md")):
            found.append(e.path)
    return found, dangling


def find_in_repo(root, depth=0):
    """SKILL.md가 있는 폴더를 찾으면 그 아래는 보지 않는다. 링크 폴더와 테스트 폴더는 건너뛴다."""
    if os.path.isfile(os.path.join(root, "SKILL.md")):
        return [root]
    found = []
    if depth < MAX_DEPTH:
        for e in scan_dirs(root):
            hidden = e.name.startswith(".") and e.name not in AGENT_DIRS
            if e.is_dir(follow_symlinks=False) and not hidden and e.name not in SKIP_DIRS:
                found += find_in_repo(e.path, depth + 1)
    return found


# ---- 머리말 읽기 ----

def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def split_front(text):
    """(머리말, 문제 코드). 머리말은 SKILL.md의 둘째 줄부터다."""
    if not re.match(r"---[ \t]*(?:\n|$)", text):
        return None, "frontmatter-missing"
    m = re.match(r"---[ \t]*\n(.*?)^---[ \t]*$", text, re.S | re.M)
    return (m.group(1), None) if m else (None, "frontmatter-unclosed")


def fields(front):
    """맨 앞 열의 '키: 값'을 읽는다. 들여쓴 줄·목록 줄은 앞 값에 붙인다. → {키: (원문, 줄)}, [(문제, 줄)]"""
    out, bad, key = {}, [], None
    for i, line in enumerate(front.split("\n"), start=2):
        if re.match(r"[ ]*\t", line) and line.strip():
            bad.append(("머리말 들여쓰기에 탭 문자가 있음", i))
        m = re.match(r"([A-Za-z_][\w-]*)[ \t]*:(?:[ \t]+(.*))?$", line)
        if m:
            key = m.group(1)
            out[key] = (m.group(2) or "", i)
        elif key and (line[:1] in (" ", "\t") or line.startswith("- ")):
            out[key] = (out[key][0] + "\n" + line.strip(), out[key][1])
        elif line.strip() and not line.startswith("#"):
            bad.append((f"'키: 값' 꼴이 아닌 줄: {line.strip()[:40]}", i))
    return out, bad


def scalar(raw, text_field):
    """YAML 값 하나를 글자로 푼다. → (값, 문제 또는 None). 흔히 깨지는 모양만 본다."""
    raw = raw.strip()
    if re.match(r"[>|][+-]?\d?[+-]?[ \t]*(?:#[^\n]*)?(?:\n|$)", raw):
        head, _, body = raw.partition("\n")
        return (body if head[0] == "|" else " ".join(body.split("\n"))).strip(), None
    for q, ok in (('"', r'"((?:[^"\\]|\\.)*)"'), ("'", r"'((?:[^']|'')*)'")):
        if raw[:1] == q:
            m = re.fullmatch(ok + r"[ \t]*(?:#.*)?", raw, re.S)
            if not m:
                return raw.strip(q), f"따옴표({q})가 닫히지 않았거나 값 안에 같은 따옴표가 있음"
            value = m.group(1).replace('\\"', '"') if q == '"' else m.group(1).replace("''", "'")
            return " ".join(value.split("\n")), None
    plain = " ".join(re.split(r"(?:^|[ \t])#", line)[0].strip() for line in raw.split("\n")).strip()
    if raw.startswith("- ") or raw[:1] and raw[0] in ("%@`[{*&!" if text_field else "%@`"):
        return plain, f"따옴표 없는 값이 '{raw[0]}'로 시작함"
    if raw[:1] not in ("[", "{") and re.search(r":(?:\s|$)", plain):
        return plain, "따옴표 없는 값 안에 ': '가 있음(엄격한 YAML 파서에서 깨짐)"
    return plain, None


# ---- 글 속의 링크와 경로 ----

def blank(pattern, text):
    """맞은 부분을 빈칸으로 바꾼다(줄 번호는 그대로)."""
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S | re.M)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def blank_code(text):
    """펜스·들여쓰기 코드·HTML 주석 줄을 빈칸으로 바꾼다. 앞 줄이 문단이면 네 칸 들여써도 문단이다(CommonMark)."""
    out, lists, fence, para = [], [], None, False   # lists: 열린 목록 항목·각주의 본문이 시작하는 칸
    comment = False
    for line in text.split("\n"):
        s = line.expandtabs(4)
        ind, body = len(s) - len(s.lstrip(" ")), s.strip()
        inner = lists[-1] if lists else 0
        if body and ind < inner:
            fence, comment = None, False   # 목록 항목이 끝나면 그 안의 펜스와 주석도 끝난다
        if comment:
            comment = "-->" not in body
            out.append(" " * len(line))
            continue
        if fence:
            if re.fullmatch(re.escape(fence) + re.escape(fence[0]) + "*", body) and ind < inner + 4:
                fence = None
            out.append(" " * len(line))
            continue
        if not body:
            para = False
            out.append(line)
            continue
        item = re.match(r" *(?:[-*+]|\d{1,9}[.)])(?: {1,4}(?! )|(?= {5})|$)", s)
        note = re.match(r" *\[\^[^\]\s]+\]:", s)   # 각주 본문은 네 칸 들여쓴다
        block = item or note or re.match(r"#{1,6}(?: |$)|```[^`]*$|~~~|<!--", body)
        while lists and ind < lists[-1] and (block or not para):
            lists.pop()
        inner = lists[-1] if lists else 0
        if ind >= inner + 4:
            out.append(line if para else " " * len(line))
            continue
        if item:
            lists.append(len(item.group(0)) + item.group(0).endswith(tuple("-*+.)")))
            body = s[item.end():].strip()
            if s[item.end():].startswith(" " * 5):   # 표시 뒤 다섯 칸부터는 항목 안의 들여쓰기 코드
                out.append(" " * len(line))
                para = False
                continue
        elif note:
            lists.append(inner + 4)
            body = s[note.end():].strip()
        if body.startswith("<!--"):   # 주석 줄은 문단이 아니다
            comment, para = "-->" not in body, False
            out.append(" " * len(line))
            continue
        f = re.match(r"(`{3,})[^`]*$|(~{3,})", body)
        fence = f and (f.group(1) or f.group(2))
        para = bool(body) and not fence and not re.match(r"#{1,6}(?: |$)|(?:=+|-+|\*{3,}|_{3,})$", body)
        out.append(" " * len(line) if fence else line)
    return "\n".join(out)


def broken_links(path):
    text = blank_code(read(path))
    for pattern in (r"<!--.*?-->", r"(`+)(?!`)[^\n]+?(?<!`)\1(?!`)"):
        text = blank(pattern, text)
    hits = list(re.finditer(r"\]\([ \t]*(?:<([^>\n]+)>|([^)\s]+))(?:[ \t]+[\"'][^\n]*?[\"'])?[ \t]*\)", text))
    hits += re.finditer(r"^ {0,3}\[[^\]^\n][^\]\n]*\]:[ \t]*(?:<([^>\n]+)>|(\S+))", text, re.M)
    for m in hits:
        target = m.group(1) or m.group(2)
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:|[#/~]", target) or re.search(r"[{}<>$*…]|\.\.\.", target):
            continue   # 웹 주소·페이지 안 위치·절대 경로·자리 표시. 점도 빗금도 없는 대상(예시 낱말)도 아래에서 거른다
        rel = unquote(re.split(r"[#?]", target)[0])
        if re.search(r"[./]", rel) and not os.path.exists(os.path.join(os.path.dirname(path), rel)):
            yield target, line_of(text, m.start())


HOME = r"(?:~|\$HOME|\$\{HOME\}|/Users/[\w.-]+|/home/[\w.-]+)"
REST = r"([A-Za-z0-9_./-]*)(?![^\x00-\x7f<{*$])"   # 뒤에 한글·자리 표시가 붙으면 경로가 잘린 것이라 보지 않는다
SKILL_REF = re.compile(HOME + r"/\.(?:claude|agents|codex|cursor)/skills/([A-Za-z0-9_.-]+)" + r"(?:/" + REST + r")?(?![\w<{*$])")
OWN_REF = re.compile(r"(?:(?<![\w/.~}>$*\"'-])|(?<![\w/.])\./|(?:<[^>\n]*(?:skill|스킬)[^>\n]*>|\$\{?\w*SKILL\w*\}?)\"?/)"
                     r"((?:scripts|references|assets)/[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.[A-Za-z0-9]{1,5})(?![\w/*<{$])", re.I)
ABS_REF = re.compile(r"(?<![\w/.:])/(?:Users|home)/([A-Za-z0-9_.-]+)(/[A-Za-z0-9_./-]*)?")


def stale_paths(text, skill_dir, by_folder, repo_mode):
    """SKILL.md에 적힌 경로 중 없는 것. (코드, 설명, 줄). 같은 경로는 처음 한 번만."""
    for m in {m.group(1): m for m in reversed(list(OWN_REF.finditer(text)))}.values():
        # 다른 스킬의 파일을 가리키거나, assets 폴더가 없는 스킬의 assets/(작업 결과물)는 낡은 경로가 아니다
        homes = [skill_dir, *(p for paths in by_folder.values() for p in paths)]
        if m.group(1).startswith("assets/") and not os.path.isdir(os.path.join(skill_dir, "assets")):
            continue
        if re.search(r"\](?:\(|:)[ \t]*<?$", text[:m.start()]):
            continue   # 마크다운 링크는 broken_links가 본다
        if not any(os.path.exists(os.path.join(h, m.group(1))) for h in homes):
            yield "stale-path", f"스킬 폴더에 없는 파일: {m.group(1)}", line_of(text, m.start())
    covered = []
    for m in SKILL_REF.finditer(text):
        name, rest = m.group(1).rstrip("."), (m.group(2) or "").rstrip(".")
        covered.append(m.span())
        targets = [os.path.join(p, rest) for p in by_folder.get(name, [])]
        if not targets and not repo_mode:
            targets = [os.path.expanduser(os.path.expandvars(m.group(0).rstrip(".")))]
        if targets and not any(os.path.exists(t) for t in targets):
            yield "stale-path", f"없는 스킬 경로: {tilde(m.group(0))}", line_of(text, m.start())
    for m in ABS_REF.finditer(text):
        if any(a <= m.start() < b for a, b in covered) and not repo_mode:
            continue
        if repo_mode:
            if m.group(1).lower() not in SAMPLE_USERS:
                yield "abs-path", "다른 컴퓨터에는 없는 홈 폴더 절대 경로", line_of(text, m.start())
        elif m.group(1).lower() not in SAMPLE_USERS and text[m.end():m.end() + 1].isascii() \
                and not os.path.exists(m.group(0).rstrip(".")):
            yield "stale-path", f"없는 경로: {tilde(m.group(0))}", line_of(text, m.start())


def triggers(desc):
    """설명에서 따옴표로 적은 말만 뽑는다."""
    found = re.findall(r"(?:^|(?<=[\s(\[,/·:;|]))(?:'([^'\n]{2,40})'|\"([^\"\n]{2,40})\")(?![A-Za-z0-9])", desc)
    found += [(x, "") for x in re.findall(r"“([^”\n]{2,40})”|‘([^’\n]{2,40})’|「([^」\n]{2,40})」", desc) for x in x if x]
    return {" ".join((a or b).split()).strip(" .,!?").casefold() for a, b in found} - {""}


# ---- 검사 ----

def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def shown(path):
    rel = os.path.relpath(path)
    return rel if not rel.startswith("..") else tilde(os.path.abspath(path))


def issue(code, level, path, line, message):
    return dict(code=code, level=level, file=shown(path), line=line, message=message)


def check(skill_dir, locations, by_folder, repo_mode, allow_names):
    path, issues = os.path.join(skill_dir, "SKILL.md"), []
    folder = os.path.basename(os.path.abspath(locations[0]))

    def add(code, level, line, message, file=path):
        issues.append(issue(code, level, file, line, message))

    text = read(path)
    rec = dict(name=folder, folder=folder, path=shown(skill_dir), locations=[shown(p) for p in locations], invocable=True,
               desc_chars=0, has_scripts=os.path.isdir(os.path.join(skill_dir, "scripts")),
               has_tests=os.path.isdir(os.path.join(skill_dir, "tests")), triggers=set())
    front, problem = split_front(text)
    if front is None:
        add(problem, "error", 1, "머리말(---)이 없음" if problem == "frontmatter-missing" else "머리말을 닫는 ---가 없음")
    else:
        found, bad = fields(front)
        for message, line in bad:
            add("frontmatter-yaml", "error", line, message)
        values = {}
        for key, (raw, line) in found.items():
            nested = not raw.split("\n")[0].strip() and "\n" in raw
            if nested and key not in TEXT_FIELDS:
                continue
            values[key], problem = scalar(raw, key in TEXT_FIELDS)
            if problem:
                add("frontmatter-yaml", "error", line, f"{key}: {problem}")
            if key not in SPEC_FIELDS:
                add("field-unknown", "warning", line, f"규격 밖 필드 {key}(일부 에이전트에서만 통하고 업로드가 거절될 수 있음)")
        for key in found.keys() - values.keys() - SPEC_FIELDS:
            add("field-unknown", "warning", found[key][1], f"규격 밖 필드 {key}(일부 에이전트에서만 통하고 업로드가 거절될 수 있음)")
        at = lambda key: found[key][1] if key in found else 1
        name, desc = values.get("name", ""), values.get("description", "")
        if not name:
            add("name-missing", "error", at("name"), "name이 없음")
        else:
            rec["name"] = name
            if name not in allow_names and (len(name) > NAME_LIMIT or not NAME_RE.fullmatch(name)):
                add("name-format", "error", at("name"), f"name은 소문자·숫자·하이픈 1~{NAME_LIMIT}자: {name}")
            for loc in locations:
                if os.path.basename(os.path.abspath(loc)) != name:
                    add("name-folder", "error", at("name"), f"name({name})이 폴더 이름({os.path.basename(os.path.abspath(loc))})과 다름")
        if not desc:
            add("description-missing", "error", at("description"), "description이 없음")
        elif len(desc) > DESC_LIMIT:
            add("description-length", "error", at("description"), f"description {len(desc)}자 > {DESC_LIMIT}자")
        if len(values.get("compatibility", "")) > COMPAT_LIMIT:
            add("compatibility-length", "error", at("compatibility"), f"compatibility {len(values['compatibility'])}자 > {COMPAT_LIMIT}자")
        rec["invocable"] = values.get("disable-model-invocation", "").lower() != "true"
        rec["desc_chars"] = len(desc) + len(values.get("when_to_use", ""))
        rec["triggers"] = triggers(desc)
    for code, message, line in stale_paths(text, skill_dir, by_folder, repo_mode):
        add(code, "warning", line, message)
    for base, dirs, files in os.walk(skill_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.lower().endswith(".md"):
                for target, line in broken_links(os.path.join(base, f)):
                    add("broken-link", "error", line, f"없는 파일로 가는 링크: {target}", os.path.join(base, f))
    return rec, issues


def lint(roots, repo_mode, allow_names):
    issues, places, per_root = [], {}, []
    for root in roots:
        found, dangling = (find_in_repo(root), []) if repo_mode else find_installed(root)
        for p in dangling:
            issues.append(issue("dangling-symlink", "error", p, 0, f"가리키는 곳이 없는 링크: {tilde(os.readlink(p))}"))
        for p in found:
            places.setdefault(os.path.realpath(p), []).append(p)   # 링크로 여러 번 설치한 스킬은 하나로 센다
        per_root.append((root, {os.path.realpath(p) for p in found}))
    by_folder = {}
    for p in (p for locs in places.values() for p in locs):
        by_folder.setdefault(os.path.basename(p), []).append(p)
    skills = {}
    for real, locs in places.items():
        rec, found = check(locs[0], locs, by_folder, repo_mode, allow_names)
        skills[real] = rec
        issues += found

    by_name, by_phrase = {}, {}
    for s in skills.values():
        by_name.setdefault(s["name"], []).append(s)
        for phrase in s["triggers"] if s["invocable"] else ():
            by_phrase.setdefault(phrase, set()).add(s["name"])
    for name, group in by_name.items():
        if len(group) > 1:
            same = len({read(os.path.join(real, "SKILL.md")) for real, s in skills.items() if s["name"] == name}) == 1
            issues.append(issue("name-duplicate", "error" if repo_mode else "warning", os.path.join(group[0]["path"], "SKILL.md"), 1,
                                f"같은 이름 {name}: {len(group)}곳, SKILL.md 내용 {'같음' if same else '다름'}: "
                                + ", ".join(s["path"] for s in group)))
    overlaps = [dict(phrase=p, skills=sorted(n)) for p, n in sorted(by_phrase.items()) if len(n) > 1]
    for o in overlaps:
        first = next(s for s in skills.values() if s["name"] == o["skills"][0])
        issues.append(issue("trigger-overlap", "warning", os.path.join(first["path"], "SKILL.md"), 1,
                            f"트리거 '{o['phrase']}'가 겹침: {', '.join(o['skills'])}"))

    issues.sort(key=lambda i: (i["level"] != "error", i["file"], i["line"], i["code"]))
    on = [s for s in skills.values() if s["invocable"]]
    return dict(
        schema=1, mode="root" if repo_mode else "installed", skills=len(skills), invocable=len(on),
        desc_chars_invocable=sum(s["desc_chars"] for s in on),
        roots=[dict(path=shown(r), skills=len(reals), invocable=sum(skills[x]["invocable"] for x in reals),
                    desc_chars_invocable=sum(skills[x]["desc_chars"] for x in reals if skills[x]["invocable"])) for r, reals in per_root],
        longest=[dict(name=s["name"], desc_chars=s["desc_chars"]) for s in sorted(on, key=lambda s: (-s["desc_chars"], s["name"]))[:5]],
        scripts_without_tests=sorted({s["name"] for s in skills.values() if s["has_scripts"] and not s["has_tests"]}),
        trigger_overlaps=overlaps,
        counts={lv: sum(i["level"] == lv for i in issues) for lv in ("error", "warning")},
        issues=issues,
        items=sorted(({k: v for k, v in s.items() if k != "triggers"} for s in skills.values()), key=lambda s: (s["name"], s["path"])))


def report(r):
    out = [f"스킬 {r['skills']}개 · 오류 {r['counts']['error']} · 경고 {r['counts']['warning']}", "",
           f"[설명 길이] 모델이 스스로 고르는 스킬 {r['invocable']}개의 설명 합계 {r['desc_chars_invocable']:,}자"]
    out += [f"  {x['path']}: 스킬 {x['skills']} · 설명이 실리는 것 {x['invocable']} · {x['desc_chars_invocable']:,}자" for x in r["roots"]]
    out.append("  긴 것: " + (", ".join(f"{x['name']} {x['desc_chars']:,}자" for x in r["longest"]) or "없음"))
    if r["scripts_without_tests"]:
        out.append("[테스트 없는 스크립트] " + ", ".join(r["scripts_without_tests"]))
    for level, title in (("error", "오류"), ("warning", "경고")):
        rows = [i for i in r["issues"] if i["level"] == level]
        if rows:
            out += ["", f"[{title} {len(rows)}]"] + [f"  {i['file']}:{i['line']} {i['code']}: {i['message']}" for i in rows]
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", action="append", help="검사할 저장소 폴더(아래 폴더까지 찾음). 여러 번 줄 수 있다")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    ap.add_argument("--allow-name", action="append", default=[], metavar="이름",
                    help="name-format만 봐 줄 이름(이미 설치된 옛 이름 등). 여러 번 줄 수 있다")
    a = ap.parse_args(argv)
    roots, seen = [], set()
    for r in a.root or INSTALLED:
        path = os.path.expanduser(r)
        if os.path.isdir(path):
            if os.path.realpath(path) not in seen:
                seen.add(os.path.realpath(path))
                roots.append(path)
        elif a.root:
            print(f"폴더가 없어요: {r}", file=sys.stderr)
            return 2
    result = lint(roots, bool(a.root), set(a.allow_name))
    if not result["skills"] and not result["issues"]:
        print("SKILL.md가 있는 폴더를 찾지 못했어요", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=1) if a.json else report(result))
    worst = result["counts"]["error"] + (result["counts"]["warning"] if a.fail_on == "warning" else 0)
    return 1 if a.fail_on != "never" and worst else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
