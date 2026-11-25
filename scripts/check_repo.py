#!/usr/bin/env python3
"""저장소 검사: 스킬 규격, 목록 일치, 링크, 새어 나가면 안 되는 값. 표준 라이브러리만 쓴다.

  python3 scripts/check_repo.py                  # 검사
  python3 scripts/check_repo.py --tests          # 스킬마다 tests/run_tests.py도 돌린다
  python3 scripts/check_repo.py --deny words.txt # 저장소 밖에 둔 금칙어 파일(한 줄에 하나)로 더 본다
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills-lint/scripts"))
sys.dont_write_bytecode = True
from skills_lint import blank_code  # noqa: E402
SPEC = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
HOST = {"disable-model-invocation", "argument-hint"}  # 호스트 전용. 쓰면 README에 이유를 적는다
LEGACY = {"presentation_slides"}  # 밑줄 이름. 설치한 사람의 경로를 깨지 않으려고 이름만 남긴다
SECRET_NAME = re.compile(r"(?:^|/)(?:\.env(?:\.(?!example$)[^/]+)?|id_(?:rsa|ed25519)|[^/]+\.(?:pem|key|p12|pfx|keystore))$")
LEAKS = [
    ("개인 절대 경로", re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/(?!(?:me|you|user|name|<[^>]+>|\$|runner|\.\.\.|…)\b)[A-Za-z0-9._-]+")),
    ("이메일", re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.|anthropic\.com|users\.noreply)[A-Za-z0-9-]+\.(?:com|net|org|io|kr|ai)\b")),
    ("개인키", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("토큰 모양", re.compile(r"\b(?:sk-(?:ant-|proj-)?[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,})")),
]
problems = []


def bad(where, what):
    problems.append(f"{where}: {what}")


def frontmatter(path):
    s = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", s, re.S)
    if not m:
        return None, s
    out, key = {}, None
    for line in m.group(1).splitlines():
        k = re.match(r"([A-Za-z-]+):\s*(.*)$", line)
        if k:
            key = k.group(1)
            v = k.group(2).strip()
            out[key] = "" if re.fullmatch(r"[>|][+-]?", v) else v.strip("'\"")
        elif key and line.startswith((" ", "\t")):  # 여러 줄 값
            out[key] = (out[key] + " " + line.strip()).strip()
    return out, s


def links(text):
    """코드 블록·인라인 코드 밖의 상대 링크. 코드 판별은 skills-lint와 같은 함수를 쓴다."""
    text = re.sub(r"`[^`\n]*`", "", blank_code(text))
    return [x for x in re.findall(r"\]\(([^)#\s]+)", text) if not re.match(r"[a-z]+:", x) and "{" not in x and "<" not in x]


def skills():
    return sorted(p.parent for p in ROOT.glob("*/SKILL.md"))


def check_skill(d):
    fm, body = frontmatter(d / "SKILL.md")
    if fm is None:
        return bad(d.name, "SKILL.md 머리말(---)이 없다")
    if fm.get("name") != d.name:
        bad(d.name, f"name({fm.get('name')})이 폴더 이름과 다르다")
    if d.name not in LEGACY and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", d.name):
        bad(d.name, "이름은 소문자·숫자·하이픈만")
    if not 1 <= len(fm.get("description", "")) <= 1024:
        bad(d.name, f"description 길이 {len(fm.get('description', ''))} (1~1024)")
    for k in fm:
        if k not in SPEC | HOST:
            bad(d.name, f"규격에 없는 필드 {k}")
    for f in d.rglob("*.md"):
        if "tests" in f.relative_to(d).parts:
            continue
        for link in links(f.read_text(encoding="utf-8")):
            if not (f.parent / link).exists():
                bad(str(f.relative_to(ROOT)), f"깨진 링크 {link}")
    return fm


def check_lists(all_skills):
    live = {d.name for d in all_skills if (frontmatter(d / "SKILL.md")[0] or {}).get("disable-model-invocation") != "true"}
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    paths = []
    for p in market["plugins"]:
        base = ROOT / p["source"] if isinstance(p.get("source"), str) and p["source"].startswith(".") else None
        if base is None or not base.is_dir():
            bad("marketplace.json", f"{p.get('name')}의 source({p.get('source')})가 없다")
            base = ROOT
        for s in p["skills"]:
            paths.append(s)
            if not (base / s / "SKILL.md").exists():
                bad("marketplace.json", f"{s}에 SKILL.md가 없다")
    listed = {Path(s).name for s in paths}
    groups = {s for g in json.loads((ROOT / "skills.sh.json").read_text(encoding="utf-8"))["groupings"] for s in g["skills"]}
    for name, have, want in (("marketplace.json", listed, live), ("skills.sh.json", groups, {d.name for d in all_skills})):
        for x in sorted(want - have):
            bad(name, f"{x}이 빠졌다")
        for x in sorted(have - want):
            bad(name, f"{x}은 없는(또는 지원 종료) 스킬이다")
    for readme in ("README.md", "README.en.md"):
        text = (ROOT / readme).read_text(encoding="utf-8") if (ROOT / readme).exists() else ""
        for x in sorted(live):
            if f"({x}/" not in text:
                bad(readme, f"{x} 링크가 없다")
    for f in ROOT.glob("*.md"):
        for link in links(f.read_text(encoding="utf-8")):
            if not (ROOT / link).exists():
                bad(f.name, f"깨진 링크 {link}")
        if "{{" in f.read_text(encoding="utf-8"):
            bad(f.name, "채우지 않은 자리표시 {{ }}")


def check_leaks(deny):
    r = subprocess.run(["git", "ls-files", "-coz", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode or not r.stdout:
        return bad("git", "파일 목록을 못 읽었다. 유출 검사를 하지 못했다")
    for rel in r.stdout.split("\0"):
        p = ROOT / rel
        if not rel:
            continue
        name = rel + (" -> " + os.readlink(p) if p.is_symlink() else "")  # 폴더 이름과 링크 대상도 공개된다
        for w in deny:
            if w.lower() in name.lower():
                bad(rel, "금칙어(경로·링크)")
        if p.is_symlink():  # 본문은 이 저장소에 실리지 않는다
            if any(rx.search(name) for _, rx in LEAKS):
                bad(rel, "링크 대상에 개인 값")
            continue
        if not p.is_file():
            continue
        if SECRET_NAME.search(rel):
            bad(rel, "비밀값 파일 이름")
        raw = p.read_bytes()
        if b"\0" in raw[:8000]:  # 이진 파일
            continue
        for n, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            if "check_repo: ok" in line:
                continue
            for what, rx in LEAKS:
                if rx.search(line):
                    bad(f"{rel}:{n}", what)
            for w in deny:
                if w.lower() in line.lower():
                    bad(f"{rel}:{n}", "금칙어")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deny")
    ap.add_argument("--tests", action="store_true")
    a = ap.parse_args()
    deny = [w.strip() for w in Path(a.deny).read_text(encoding="utf-8").splitlines() if w.strip()] if a.deny else []
    found = skills()
    for d in found:
        check_skill(d)
    check_lists(found)
    check_leaks(deny)
    if a.tests:
        for d in found:
            t = d / "tests/run_tests.py"
            if t.exists():
                r = subprocess.run([sys.executable, str(t)], cwd=d, capture_output=True, text=True, timeout=600)
                print(("통과 " if r.returncode == 0 else "실패 ") + d.name)
                if r.returncode:
                    bad(d.name, "tests/run_tests.py 실패\n" + (r.stdout + r.stderr)[-1500:])
    print("\n".join(problems) or "문제 없음")
    print(f"스킬 {len(found)}개 · 문제 {len(problems)}개")
    return bool(problems)


sys.exit(main())
