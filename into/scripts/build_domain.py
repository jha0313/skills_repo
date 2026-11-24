#!/usr/bin/env python3
"""domain-expert 허브를 만들고 커리큘럼을 검사한다.

사용: python3 -I build_domain.py <과정 폴더> [--check]
  <과정 폴더>/curriculum.json + lessons/ → <과정 폴더>/index.html
  --check  만들지 않고 검사만 한다. FAIL이 하나라도 있으면 종료 코드 1.
검사는 빠진 칸·끊긴 연결·없는 파일·문항 수만 본다. 사실과 순서는 사람이 대조한다.
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = {"eli5", "ste", "doc", "html", "interactive", "slides", "test", "shorts", "video", "source"}
FAIL, WARN = [], []


def inline(t):
    t = html.escape(t, quote=False)
    keep = []
    t = re.sub(r"`([^`]+)`", lambda m: keep.append(m[1]) or f"\0{len(keep)-1}\0", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return re.sub(r"\0(\d+)\0", lambda m: f"<code>{keep[int(m[1])]}</code>", t)


def md(src):
    """레슨용 작은 마크다운 변환기: 제목·문단·목록(2단)·표·인용·코드·가로줄."""
    out, L, i = [], src.replace("\r", "").split("\n"), 0
    while i < len(L):
        s = L[i]
        if s.startswith("```"):
            j = i + 1
            while j < len(L) and not L[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(L[i + 1:j])) + "</pre>"); i = j + 1
        elif re.match(r"#{1,6} ", s):
            n = len(s) - len(s.lstrip("#")); out.append(f"<h{min(n,3)}>{inline(s[n+1:])}</h{min(n,3)}>"); i += 1
        elif re.match(r"\s*(---|\*\*\*)\s*$", s):
            out.append("<hr>"); i += 1
        elif s.lstrip().startswith("|") and i + 1 < len(L) and re.match(r"\s*\|[\s:|-]+\|?\s*$", L[i + 1]):
            cell = lambda r: [c.replace("\x01", "|") for c in r.strip().replace("\\|", "\x01").strip("|").split("|")]
            h = cell(s); rows = []; i += 2
            while i < len(L) and L[i].lstrip().startswith("|"):
                rows.append(cell(L[i])); i += 1
            out.append('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{inline(c.strip())}</th>" for c in h) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")
        elif s.startswith(">"):
            b = []
            while i < len(L) and L[i].startswith(">"):
                b.append(inline(L[i].lstrip("> "))); i += 1
            out.append("<blockquote>" + "<br>".join(b) + "</blockquote>")
        elif re.match(r"\s*([-*]|\d+\.) ", s):
            stack = []
            while i < len(L) and (re.match(r"\s*([-*]|\d+\.) ", L[i]) or (L[i].startswith("  ") and L[i].strip())):
                m = re.match(r"(\s*)([-*]|(\d+)\.) (.*)", L[i])
                if not m:
                    out.append("<br>" + inline(L[i].strip())); i += 1; continue
                d, t = len(m[1]), "ol" if m[3] else "ul"
                while stack and stack[-1][0] > d:
                    out.append(f"</li></{stack.pop()[1]}>")
                if stack and stack[-1][0] == d:
                    if stack[-1][1] != t:
                        out.append(f"</li></{stack.pop()[1]}>"); stack.append((d, t)); out.append(f'<{t}{" start=" + m[3] if m[3] else ""}><li>')
                    else:
                        out.append("</li><li>")
                else:
                    stack.append((d, t)); out.append(f'<{t}{" start=" + m[3] if m[3] and m[3] != "1" else ""}><li>')
                out.append(inline(m[4])); i += 1
            while stack:
                out.append(f"</li></{stack.pop()[1]}>")
        elif not s.strip():
            i += 1
        else:
            b = []
            while i < len(L) and L[i].strip() and not re.match(r"(#{1,6} |```|>|\s*([-*]|\d+\.) |\s*\|)", L[i]):
                b.append(inline(L[i])); i += 1
            if not b:
                b = [inline(L[i])]; i += 1
            out.append("<p>" + "<br>".join(b) + "</p>")
    return "\n".join(out)


def need(o, keys, where):
    for k in keys:
        if o.get(k) in (None, "", [], {}):
            FAIL.append(f"{where}: '{k}' 비어 있음")


def quiz(root, g, where, parts=None):
    f = g.get("file")
    if not f:
        WARN.append(f"{where}: 퀴즈 파일 없음(명령만 보인다)"); return
    p = os.path.join(root, f)
    if not os.path.exists(p):
        FAIL.append(f"{where}: {f} 없음"); return
    s = open(p, encoding="utf-8").read()
    if '"into-test"' not in s:
        FAIL.append(f"{where}: {f} 가 점수를 보내지 않는다(assets/test.html 최신 동작 코드로 바꾼다)")
    a = s.find("const QUIZ = "); b = s.find("// ===== 동작 코드")
    if where == "졸업 시험" and not re.search(r'^\s*"?exam"?\s*:\s*true', s[a:b], re.M):
        FAIL.append(f"{where}: {f} 의 QUIZ에 exam: true 가 없다(풀다가 닫으면 첫 점수가 남지 않는다)")
    rv = re.search(r'\brev"?\s*:\s*(\d+)', s[a:b])
    if where == "졸업 시험" and int(rv[1] if rv else 1) != int(g.get("rev") or 1):
        FAIL.append(f"{where}: {f} 의 rev {rv[1] if rv else 1} ≠ final.rev {g.get('rev') or 1}")
    if where == "졸업 시험" and "into-exam" not in s:
        FAIL.append(f"{where}: {f} 동작 코드가 옛 것이다(assets/test.html 최신 동작 코드로 바꾼다)")
    n = len(re.findall(r"\btype:\s*\"(?:choice|predict)\"|\"type\":\s*\"(?:choice|predict)\"", s[a:b]))
    if n != g.get("total"):
        FAIL.append(f"{where}: total {g.get('total')} ≠ 실제 문항 {n}")
    if parts is not None:
        got = re.findall(r"\"?section\"?:\s*\"([A-Za-z]+\d+)", s[a:b])
        miss = [x for x in parts if x not in got]
        if miss:
            FAIL.append(f"{where}: 문항이 없는 섹션 {miss} (문항의 section을 'E1 제목'처럼 섹션 id로 시작한다)")


def words(root, g):
    """시험 한 벌에서 섹션 id → 백틱으로 감싼 낱말(6자 이상)."""
    p = os.path.join(root, g.get("file") or "-"); out = {}
    if os.path.isfile(p):
        s = open(p, encoding="utf-8").read(); s = s[s.find("const QUIZ = "):s.find("// ===== 동작 코드")]
        for part in re.split(r"\"?section\"?:\s*(?=\")", s)[1:]:
            k = re.match(r'"([A-Za-z]+\d+)?', part)[1]
            out.setdefault(k, set()).update(w for w in re.findall(r"`([^`\n]{6,60})`", part))
    return out


def deliverable(d, where):
    need(d, ["what", "form", "rubric", "pass", "answer"], where)
    if len(d.get("rubric", [])) < 3:
        FAIL.append(f"{where}: 채점표 항목 3개 미만")
    if not isinstance(d.get("pass"), int) or d.get("pass", 0) > len(d.get("rubric", [])):
        FAIL.append(f"{where}: pass는 채점표 개수 이하의 정수")
    for r in d.get("rubric", []):
        r = r if isinstance(r, str) else r.get("t", "")
        if re.search(r"잘 (썼|이해|설명)|충분히|적절(히|한)|깊이 있|명확하게 이해", r):
            WARN.append(f"{where}: 채점표가 흐리다 — {r[:50]}")


def main():
    root = os.path.abspath(sys.argv[1]); C = json.load(open(os.path.join(root, "curriculum.json"), encoding="utf-8"))
    need(C, ["slug", "domain", "kind", "asof", "learner", "vision", "strategy", "goal", "kpis", "levels", "diag", "final", "capstone", "sources", "honesty", "missing", "source_line", "onepage"], "과정")
    for k in ("vision", "strategy", "goal"):
        if not isinstance(C.get(k), str):
            FAIL.append(f"과정: {k}는 하나(문장)여야 한다")
    if C.get("kind") == "repo" and "cases" not in C:
        C["cases"] = []
    kp = {k["id"]: k for k in C["kpis"]}
    if not 3 <= len(kp) <= 6:
        FAIL.append(f"지표 {len(kp)}개 (3~6개)")
    for k in C["kpis"]:
        need(k, ["name", "why", "measure", "unit", "target", "source"], f"지표 {k.get('id')}")
        if k.get("source") not in ("exam", "gates", "deliverables", "manual"):
            FAIL.append(f"지표 {k['id']}: source는 exam·gates·deliverables·manual")
        if k.get("start") and k["start"] not in [s["id"] for l in C["levels"] for s in l["sections"]]:
            FAIL.append(f"지표 {k['id']}: start {k['start']} 섹션이 없다")
    if not any(k["source"] == "manual" for k in C["kpis"]):
        FAIL.append("지표가 모두 과정 안의 점수다. 실제로 해 보고 재는 지표(manual)가 하나 이상 있어야 한다")
    if [l["name"].split()[0] for l in C["levels"]] != ["Easy", "Medium", "Hard", "심화"]:
        FAIL.append("단계 이름·순서는 Easy → Medium → Hard → 심화")
    src = {s["id"] for s in C["sources"]}
    for s in C["sources"]:
        need(s, ["id", "title", "type", "grade", "finding"], f"출처 {s.get('id')}")
        if s.get("grade") not in ("A", "B", "C", "D"):
            FAIL.append(f"출처 {s.get('id')}: grade는 A~D")
    secs = [s for l in C["levels"] for s in l["sections"]]; ids = [s["id"] for s in secs]
    if len(set(ids)) != len(ids):
        FAIL.append("섹션 id가 겹친다")
    if not 8 <= len(secs) <= 14:
        WARN.append(f"섹션 {len(secs)}개 (8~14개 권장)")
    raised, modes, hours, seen, vis = set(), {}, 0, set(), []
    for s in secs:
        w = s["id"]
        need(s, ["title", "question", "vision", "strategy", "goal", "deliverable", "kpi", "lessons", "gate", "hours", "ask"], w)
        for k in ("vision", "strategy", "goal"):
            if not isinstance(s.get(k), str):
                FAIL.append(f"{w}: {k}는 하나(문장)여야 한다")
        vis.append(s.get("vision"))
        for n in s.get("needs", []):
            if n not in seen:
                FAIL.append(f"{w}: 먼저 할 섹션 {n}이 앞에 없다")
        seen.add(w); hours += s.get("hours", 0)
        for k in s.get("kpi", []):
            if k["id"] not in kp:
                FAIL.append(f"{w}: 없는 지표 {k['id']}")
            raised.add(k["id"]); need(k, ["from", "to"], f"{w} 지표 {k['id']}")
        deliverable(s["deliverable"], w + " 결과물")
        if not 2 <= len(s["lessons"]) <= 4:
            WARN.append(f"{w}: 레슨 {len(s['lessons'])}개 (2~4개 권장)")
        if len({l["mode"] for l in s["lessons"]}) < 2:
            FAIL.append(f"{w}: 레슨 형식이 한 가지뿐")
        for j, l in enumerate(s["lessons"]):
            t = f"{w} 레슨{j+1}"; need(l, ["mode", "title", "why", "min"], t); modes[l["mode"]] = modes.get(l["mode"], 0) + 1
            if l["mode"] not in MODES:
                FAIL.append(f"{t}: 없는 형식 {l['mode']}")
            if l.get("file"):
                p = os.path.join(root, l["file"])
                if not os.path.exists(p):
                    FAIL.append(f"{t}: {l['file']} 없음"); continue
                if l["file"].endswith(".md"):
                    v = l["file"][:-3] + ".view.html"
                    if os.path.exists(os.path.join(root, v)):
                        l["file"] = v
                    else:
                        l["html"] = md(open(p, encoding="utf-8").read())
            elif not l.get("cmd") and not l.get("url"):
                FAIL.append(f"{t}: file·url·cmd 중 하나가 있어야 한다")
        quiz(root, s["gate"], w + " 게이트")
        if s["gate"].get("pass", 0) < 0.7 * s["gate"].get("total", 0):
            WARN.append(f"{w}: 게이트 기준이 70% 미만")
        for x in s.get("sources", []):
            if x not in src:
                FAIL.append(f"{w}: 없는 출처 {x}")
    if len(set(vis)) != len(vis):
        FAIL.append("섹션 비전이 서로 같다")
    for k in kp.values():
        if k["id"] not in raised and k["source"] == "manual":
            FAIL.append(f"지표 {k['id']}를 올리는 섹션이 없다")
    for k, n in (("gates", len(secs)), ("deliverables", len(secs) + 1)):
        for x in C["kpis"]:
            if x["source"] == k and x["target"] != n:
                FAIL.append(f"지표 {x['id']}: 목표 {x['target']} ≠ {k} 수 {n}")
    for x in C["kpis"]:
        want = round(C["final"].get("pass", 0) / max(1, C["final"].get("total", 1)) * 100)
        if x["source"] == "exam" and abs(x["target"] - want) > 1:
            FAIL.append(f"지표 {x['id']}: 목표 {x['target']}% ≠ 졸업 시험 기준 {C['final'].get('pass')}/{C['final'].get('total')}({want}%)")
    if not any(isinstance(r, dict) and r.get("must") for r in C["capstone"].get("rubric", [])):
        FAIL.append("졸업 과제: 다른 사람·실제 사용으로 확인하는 필수 항목({\"t\": …, \"must\": true})이 하나 이상 있어야 한다")
    if len(C.get("proof", [])) < 2:
        FAIL.append("과정: proof(비전의 행동마다 남는 증거)가 2개 미만")
    rub = {s["id"]: s["deliverable"]["rubric"] for l in C["levels"] for s in l["sections"]}; rub["capstone"] = C["capstone"]["rubric"]
    for x in C.get("proof", []):
        if not x.get("need"):
            FAIL.append(f"proof '{x.get('act')}': need(빠지면 졸업이 막히는 필수 항목 또는 manual 지표)가 없다")
        for n in x.get("need", []):
            sid, _, i = n.partition(":")
            if not i:
                ok = any(k["id"] == sid and k["source"] == "manual" for k in C["kpis"])
            else:
                r = rub.get(sid, []); ok = i.isdigit() and 1 <= int(i) <= len(r) and isinstance(r[int(i) - 1], dict) and r[int(i) - 1].get("must")
            if not ok:
                FAIL.append(f"proof '{x.get('act')}': need {n} 는 must 항목도 manual 지표도 아니다(빼도 졸업한다)")
    led = "".join(open(os.path.join(root, "research", f), encoding="utf-8").read() for f in sorted(os.listdir(os.path.join(root, "research"))) if f.endswith(".md")) if os.path.isdir(os.path.join(root, "research")) else ""
    hid = [k for x in C["sources"] if x.get("hold") for k in [x["id"]] + (x.get("aka") or []) if re.search(r"^\|\s*\**" + re.escape(k) + r"\**\s*\|", led, re.M)]
    if hid:
        WARN.append(f"졸업 시험 전용(hold) 행이 과정 폴더의 장부에 그대로 있다: {hid[:12]} (과정 안의 장부에서 빼고 전체 장부는 <과정>-author에 둔다)")
    for f in sorted(os.listdir(os.path.join(root, "lessons"))) if os.path.isdir(os.path.join(root, "lessons")) else []:
        if f.endswith((".view.html", ".md")):
            t = open(os.path.join(root, "lessons", f), encoding="utf-8").read(); bad = [w for w in ("CLAUDE.md", "AGENTS.md", "blueprint", "설계자가", "렌더하지 않았다") if w in t and C.get("kind") == "web"]
            if bad:
                WARN.append(f"lessons/{f}: 만든 사람의 메모가 학습자에게 보인다 {bad}")
    for s in secs:
        for u in s.get("uses", []):
            if u.get("from") not in seen:
                FAIL.append(f"{s['id']}: uses의 {u.get('from')} 섹션이 없다")
        if s.get("needs") and not s.get("uses"):
            WARN.append(f"{s['id']}: 먼저 할 섹션은 있는데 uses(앞 결과물에서 가져올 것)가 없다")
    known = {k for x in C["sources"] for k in [x["id"], *x.get("aka", [])]} | set(ids) | set(kp) | {c.get("id") for c in C.get("cases", [])}
    pref = {re.match(r"[A-Za-z]+", k)[0] for k in known if re.match(r"[A-Za-z]+\d{2}$", k)}
    lost = sorted({m for m in re.findall(r"(?<![A-Za-z0-9`/._-])([A-Z]{1,3}\d{2})(?![A-Za-z0-9])", json.dumps({k: v for k, v in C.items() if k != "sources"}, ensure_ascii=False)) if re.match(r"[A-Za-z]+", m)[0] in pref and m not in known})
    if lost:
        FAIL.append(f"출처 표에서 찾을 수 없는 장부 id {lost[:12]} (aka에 적는다)")
    if C.get("kind") != "repo" and not any(x.get("hold") for x in C["sources"]):
        WARN.append("hold(졸업 시험 전용) 출처가 없다. 졸업 문항의 근거가 시험 전에 출처 표에 보이지 않는지 본다")
    pub = [("curriculum.json", json.dumps(C, ensure_ascii=False))]
    ld = os.path.join(root, "lessons")
    pub += [(f, open(os.path.join(ld, f), encoding="utf-8", errors="ignore").read()) for f in sorted(os.listdir(ld)) if f.endswith((".md", ".html"))] if os.path.isdir(ld) else []
    for f, t in pub:
        if re.search(r"/(Users|home)/[A-Za-z][\w.-]+/", t):
            FAIL.append(f"{f}: 내 컴퓨터 경로가 남아 있다")
    for d in sorted(os.listdir(root)):
        if os.path.isdir(os.path.join(root, d)) and d not in ("lessons", "research", "assets"):
            WARN.append(f"과정 폴더에 다른 폴더가 있다: {d} (임시 폴더는 공유 전에 뺀다)")
    for d, _, fs in os.walk(root):
        for f in fs:
            if f == "blueprint.md" or (f.endswith((".md", ".txt", ".json")) and re.search(r"정답\s*(위치|자리|배열|순서)[^\n]*(?:\b[A-D]\b[^A-Za-z\n]{0,4}){4}", open(os.path.join(d, f), encoding="utf-8", errors="ignore").read())):
                FAIL.append(f"{os.path.relpath(os.path.join(d, f), root)}: 시험 설계·정답이 과정 폴더 안에 있다. 과정 폴더 옆의 <과정 폴더 이름>-author/로 옮긴다")
    if os.path.exists(os.path.join(root, "deny.txt")):
        FAIL.append("deny.txt가 과정 폴더 안에 있다. 과정 폴더 옆의 <과정 폴더 이름>.deny.txt로 옮긴다(함께 공유되지 않게)")
    deny = root + ".deny.txt"
    if os.path.exists(deny):
        bad = [w.strip() for w in open(deny, encoding="utf-8") if w.strip()]
        texts = pub
        for f, t in texts:
            hit = [w for w in bad if w.lower() in t.lower()]
            if hit:
                FAIL.append(f"{f}: 검사 목록의 낱말이 남아 있다 {hit[:3]}")
    quiz(root, C["diag"], "진단", ids); quiz(root, C["final"], "졸업 시험", ids)
    cnt = {}
    for n, g in (("진단", C["diag"]), ("졸업", C["final"])):
        p = os.path.join(root, g.get("file") or "-"); t = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
        t = t[t.find("const QUIZ = "):t.find("// ===== 동작 코드")]; cnt[n] = {}
        for k in re.findall(r"\"?section\"?:\s*\"([A-Za-z]+\d+)", t):
            cnt[n][k] = cnt[n].get(k, 0) + 1
    if cnt["진단"] and cnt["졸업"] and cnt["진단"] != cnt["졸업"]:
        FAIL.append(f"진단과 졸업의 섹션 배분이 다르다: {[(k, cnt['진단'].get(k, 0), cnt['졸업'].get(k, 0)) for k in ids if cnt['진단'].get(k, 0) != cnt['졸업'].get(k, 0)]}")
    for x in secs:
        if x["gate"].get("file") and not 5 <= x["gate"].get("total", 0) <= 8:
            WARN.append(f"{x['id']}: 게이트 {x['gate'].get('total')}문항 (5~8)")
    if not C["capstone"].get("hours"):
        FAIL.append("졸업 과제: hours가 없다(전체 시간에서 빠진다)")
    if C["diag"].get("total") != C["final"].get("total"):
        FAIL.append("진단과 졸업 시험의 문항 수가 다르다(같은 설계, 다른 문제여야 앞뒤를 잰다)")
    if C["diag"].get("file") and C["diag"].get("file") == C["final"].get("file"):
        FAIL.append("진단과 졸업 시험이 같은 파일이다")
    dw, fw, same = words(root, C["diag"]), words(root, C["final"]), []
    for x in secs:
        gw = set().union(*words(root, x["gate"]).values())
        for n, hit in (("진단·졸업", dw.get(x["id"], set()) & fw.get(x["id"], set())), ("진단·게이트", dw.get(x["id"], set()) & gw), ("게이트·졸업", gw & fw.get(x["id"], set()))):
            if hit:
                same.append(f"{x['id']} {n} {sorted(hit)[:4]}")
    need(C["capstone"], ["what"], "졸업 과제"); deliverable(C["capstone"], "졸업 과제")
    if C.get("kind") != "repo":
        cs = C.get("cases", []); r = [c.get("result") for c in cs]; z = {c.get("size") for c in cs}
        if r.count("성공") < 3 or r.count("실패") < 3:
            FAIL.append(f"사례: 성공 {r.count('성공')} · 실패 {r.count('실패')} (각 3개 이상)")
        for c in cs:
            need(c, ["title", "what", "result", "size", "grade", "sources"], f"사례 {c.get('id')}")
            for x in c.get("sources", []):
                if x not in src:
                    FAIL.append(f"사례 {c.get('id')}: 없는 출처 {x}")
        if len(z) < 3:
            FAIL.append(f"사례 규모가 {sorted(map(str, z))}뿐 (대기업·중견·중소·스타트업 등 3가지 이상)")
    if len([m for m in modes if modes[m]]) < 6:
        WARN.append(f"쓴 형식 {sorted(modes)} (6가지 이상 권장)")
    for m in FAIL:
        print("FAIL", m)
    for m in WARN:
        print("WARN", m)
    if same:
        print("INFO 두 시험이 같은 낱말을 쓴다. 한쪽 해설이 다른 쪽 답을 알려 주지 않는지 본다:", " / ".join(same))
    print(f"섹션 {len(secs)} · 레슨 {sum(modes.values())} {modes} · 시간 {hours} · 출처 {len(src)} · 사례 {len(C.get('cases', []))} · FAIL {len(FAIL)} · WARN {len(WARN)}")
    if "--check" not in sys.argv:
        t = open(os.path.join(HERE, "..", "assets", "domain-expert.html"), encoding="utf-8").read()
        data = json.dumps(C, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\u0021--")
        out = os.path.join(root, "index.html"); open(out, "w", encoding="utf-8").write(t.replace("/*COURSE*/", data)); print(out)
    sys.exit(1 if FAIL else 0)


main()
