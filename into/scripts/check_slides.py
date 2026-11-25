#!/usr/bin/env python3
"""into slides 정적 점검(브라우저 없이). python3 -I check_slides.py <slides.html>

JSON·간선·단계·sim 판정표·영상 파일·글 양·그림 수를 본다. 넘침·겹침은 check_slides.cjs나 눈으로 본다.
"""
import html
import itertools
import json
import os
import re
import sys

DIAGRAM = {"flow", "sequence", "motion-inline", "timeline", "map"}
INTERACTIVE = {"sim", "predict", "compare", "timeline", "map"}
MOTION = {"motion", "motion-inline"}


def arr(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def problems(kind, d, base):
    """(FAIL 목록, WARN 목록)"""
    f, w = [], []
    if kind in ("flow", "motion-inline"):
        ids = {n["id"] for n in d["nodes"]}
        keys = {e["from"] + ">" + e["to"] for e in d["edges"]} | {e.get("id") for e in d["edges"]}
        f += ["없는 노드 " + e["from"] + ">" + e["to"] for e in d["edges"] if not {e["from"], e["to"]} <= ids]
        used = [k for s in d.get("steps", []) for k in arr(s.get("on"))] + d.get("path", [])
        f += ["없는 간선 " + k for k in used if k not in keys]
        if kind == "motion-inline" and not d.get("path"):
            f.append("path가 없다")
    elif kind == "sequence":
        ids = {a["id"] for a in d["actors"]}
        f += ["없는 참여자 " + str(m.get("from")) for m in d["msgs"] if m.get("from") not in ids or m.get("to", m["from"]) not in ids]
    elif kind == "sim":
        ctl, used, miss = d["controls"], set(), 0
        for combo in itertools.product(*[c["opts"] for c in ctl]):
            v = dict(zip([c["id"] for c in ctl], combo))
            hit = next((i for i, r in enumerate(d["rules"]) if all(v[k] in arr(x) for k, x in r.get("if", {}).items())), None)
            if hit is None:
                miss += 1
            used.add(hit)
        if miss:
            f.append("sim 규칙이 없는 조합 %d개" % miss)
        if set(range(len(d["rules"]))) - used:
            w.append("안 걸리는 sim 규칙 %s" % sorted(set(range(len(d["rules"]))) - used))
        if not d.get("scope"):
            f.append("sim에 scope(범위·뺀 조건)가 없다")
    elif kind == "chart" and not d.get("axis"):
        w.append("chart에 axis(무엇·분모·시점)가 없다")
    elif kind == "predict" and not 0 <= d["a"] < len(d["opts"]):
        f.append("predict 답 번호가 보기 밖이다")
    elif kind == "motion":
        for p in (d.get("src"), d.get("poster")):
            if not p or not os.path.exists(os.path.join(base, p)):
                f.append("파일이 없다 %s" % p)
    return f, w


def inspect(src, base):
    """(장 목록, 그림 수, FAIL 목록, WARN 목록)"""
    body = src.split("// ===== 아래는 동작 코드")[0]
    fails, warns, rows, count = [], [], [], {}
    slides = re.findall(r'<section class="slide[^"]*"[^>]*>(.*?)</section>', body, re.S)
    for url in re.findall(r'<(?:script|img|video|source|link|iframe)\b[^>]*?(?:src|href)="((?:https?:)?//[^"]+)"', body):
        fails.append("외부 자원 " + url)
    for i, s in enumerate(slides, 1):
        at, kinds = "%d장: " % i, []
        for kind, raw in re.findall(r'<div class="viz"[^>]*data-viz="([^"]+)"[^>]*>\s*<script type="application/json">(.*?)</script>', s, re.S):
            kinds.append(kind)
            count[kind] = count.get(kind, 0) + 1
            try:
                f, w = problems(kind, json.loads(raw), base)
            except (ValueError, KeyError, TypeError) as e:
                f, w = ["%s 데이터 오류 %s: %s" % (kind, type(e).__name__, e)], []
            fails += [at + m for m in f]
            warns += [at + m for m in w]
        kick = "".join(re.findall(r'<p class="kicker">(.*?)</p>', s, re.S))
        rest = re.sub(r'<script.*?</script>|<aside class="notes">.*?</aside>|<p class="(?:kicker|src|next-q|notice)">.*?</p>', " ", s, flags=re.S)
        words, title = len(text(rest).split()), text("".join(re.findall(r"<h[12][^>]*>(.*?)</h[12]>", s, re.S)))
        notes = text("".join(re.findall(r'<aside class="notes">(.*?)</aside>', s, re.S)))
        if not kinds and "정리" not in kick:
            fails.append(at + "그림이 없다")
        if words > 60:
            fails.append(at + "본문 %d단어" % words)
        elif words > 40:
            warns.append(at + "본문 %d단어(35단어 안팎)" % words)
        if not notes:
            fails.append(at + "발표자 노트가 없다")
        elif "근거" not in notes:
            warns.append(at + "노트에 근거 위치가 없다")
        if "next-q" not in s and i < len(slides):
            warns.append(at + "다음 질문이 없다")
        if "{{" in s:
            fails.append(at + "자리 표시 {{…}}가 남았다")
        rows.append((i, kinds, words, title))

    def has(group):
        return sum(1 for r in rows if group & set(r[1]))
    for ok, m in ((len(count) >= 5, "그림 종류 %d가지(5가지 이상)" % len(count)), (has(DIAGRAM) >= 3, "다이어그램 %d장(3장 이상)" % has(DIAGRAM)),
                  (has(INTERACTIVE) >= 3, "상호작용 %d장(3장 이상)" % has(INTERACTIVE)), (has(MOTION) >= 2, "모션 %d장(2장 이상)" % has(MOTION))):
        if not ok:
            (warns if len(slides) < 8 else fails).append(m)
    if "chart" not in count:
        warns.append("차트가 없다: 원문에 비교할 수가 2개 이상이면 넣고, 없으면 이유를 적는다")
    if "motion" not in count:
        warns.append("MP4 영상이 없다: 영상 도구가 있으면 1개 이상")
    return rows, count, fails, warns


def main(path):
    with open(path, encoding="utf-8") as f:
        rows, count, fails, warns = inspect(f.read(), os.path.dirname(os.path.abspath(path)))
    print("%s: %d장(정적 점검)" % (os.path.basename(path), len(rows)))
    for i, k, n, t in rows:
        print("  %2d %-14s 본문 %d단어  %s" % (i, "+".join(k) or "-", n, t[:46]))
    print("그림: " + ", ".join("%s %d" % x for x in count.items()))
    for m in fails:
        print("FAIL " + m)
    for m in warns:
        print("WARN " + m)
    print("결과: FAIL %d, WARN %d" % (len(fails), len(warns)))
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("쓰는 법: python3 -I check_slides.py <slides.html>")
    sys.exit(main(sys.argv[1]))
