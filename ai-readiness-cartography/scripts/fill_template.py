#!/usr/bin/env python3
"""score.json의 값으로 assets/template.html 복사본을 채우고, 남은 {{자리}}를 검사한다.

    python3 -I fill_template.py score.json -o map.html   # 숫자·라벨을 채우고 글로 쓸 자리를 알려 준다
    python3 -I fill_template.py --check map.html         # 남은 {{자리}}가 있으면 종료 코드 1

막대 폭·색·등급 문구는 여기서 계산한다. 템플릿 원본에는 절대 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"
RE_SLOT = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")

# 화면 라벨: 템플릿의 {{T_*}} 자리 (ko, en)
LABELS: dict[str, tuple[str, str]] = {
    "T_EYEBROW": ("저장소 점검 · AI 준비도", "Repository audit · AI-readiness"),
    "T_TITLE": ("AI 준비도 지도", "AI-Readiness Map"),
    "T_SUBTITLE": ("7개 카테고리 점수 · 구조 지도 · 먼저 할 일", "7-category score · structural map · what to do first"),
    "T_SCORED": ("측정일", "Scored"),
    "T_BRANCH": ("브랜치", "Branch"),
    "T_MODULES": ("모듈", "Modules"),
    "T_CONTEXT_FILES": ("context 파일", "context files"),
    "T_INDEX": ("AI 준비도 점수", "AI-readiness score"),
    "T_STAT_COVERED": ("context 있는 모듈", "Modules with context"),
    "T_STAT_REFS": ("없는 경로 후보", "Missing-path candidates"),
    "T_STAT_LARGE": ("300줄 넘는 파일", "Files over 300 lines"),
    "T_BARS": ("카테고리별 점수", "Score by category"),
    "T_GOOD": ("75% 이상", "75% or more"),
    "T_WARN": ("50–74%", "50–74%"),
    "T_BAD": ("50% 미만", "under 50%"),
    "T_A": ("AI 탐색과 안내", "AI navigation & coverage"),
    "T_B": ("context 문서 품질", "Context document quality"),
    "T_C": ("숨은 지식 문서화", "Tribal knowledge externalization"),
    "T_D": ("모듈 간 의존성 지도", "Cross-module dependency mapping"),
    "T_E": ("검증과 품질 관문", "Verification & quality gates"),
    "T_F": ("최신 상태 유지", "Freshness & self-maintenance"),
    "T_G": ("에이전트 성과 측정", "Agent performance outcomes"),
    "T_MAP": ("구조 지도", "Structural map"),
    "T_MAP_SUB": ("카드 = 폴더 · 선 = 의존성 · 숫자 = 줄 수", "card = directory · line = dependency · number = lines"),
    "T_LEG_CONTEXT": ("context 있음", "has context"),
    "T_LEG_TEST": ("테스트", "tests"),
    "T_LEG_REF": ("없는 경로 후보", "missing-path candidate"),
    "T_LEG_WARM": ("301–400줄", "301–400 lines"),
    "T_LEG_HOT": ("400줄 초과", "over 400 lines"),
    "T_LEG_EDGE": ("의존성", "dependency"),
    "T_WINS": ("강점", "Wins"),
    "T_WINS_SUB": ("지킬 것", "keep"),
    "T_ACTIONS": ("먼저 할 일", "Top actions"),
    "T_ACTIONS_SUB": ("순서 = 영향 ÷ 시간 (둘 다 추정)", "order = impact ÷ hours (both estimates)"),
}
GRADES = {
    "AI-Native": ("에이전트가 대부분 스스로", "agents run most work"),
    "AI-Ready": ("에이전트와 일하기 좋음", "agents work reliably"),
    "AI-Assisted": ("사람의 설명이 필요함", "needs human context"),
    "AI-Fragile": ("쉬운 일만 안전함", "safe for simple tasks only"),
    "AI-Hostile": ("에이전트가 추측으로 일함", "agents have to guess"),
}


def bar_class(ratio: float) -> str:
    return "bar-good" if ratio >= 0.75 else "bar-warn" if ratio >= 0.5 else "bar-bad"


def sub_scores(category: dict) -> str:
    return " · ".join(f"{html.escape(k)} {v}".replace("_", " ").replace(" ", "&nbsp;") for k, v in category["sub_scores"].items())


def action_items(actions: list[dict], lang: int) -> str:
    unit = ("시간", "h")[lang]
    return "\n".join(
        f'<li><div class="head"><span class="tag tag-rule">{html.escape(a["category"])} · {html.escape(a["effort"])}</span>'
        f'{html.escape(a["title"])}</div>'
        f'<div class="note">{a["effort_hours"]:g}{unit} · {html.escape(a["impact"])}</div></li>'
        for a in actions[:7]
    )


def auto_values(score: dict) -> dict[str, str]:
    """score.json만으로 정해지는 자리."""
    meta, cats = score["meta"], score["categories"]
    lang = ("ko", "en").index(meta["lang"])
    values = {
        "LANG": meta["lang"],
        "REPO_NAME": html.escape(meta["repo"]),
        "SCORED_AT": meta["scored_at"],
        "GIT_BRANCH": html.escape(meta["git_branch"]),
        "RUBRIC_VERSION": html.escape(meta["rubric_version"]),
        "MODULES_TOTAL": str(meta["modules_total"]),
        "CONTEXT_FILES_TOTAL": str(meta["context_files_total"]),
        "TOTAL_SCORE": str(score["total"]),
        "GRADE": f'{score["grade"]} · {GRADES[score["grade"]][lang]}',
        "GRADE_COLOR": score["grade_color"],
        "COVERED_MODULES": str(cats["A"]["evidence"]["covered_modules"]),
        "BROKEN_REFS": str(cats["E"]["evidence"]["ref_broken"]),
        "LARGE_FILES": str(meta["large_files_300plus"]),
        "B_SUBS": sub_scores(cats["B"]),
        "E_SUBS": sub_scores(cats["E"]),
        "ACTION_ITEMS": action_items(score["actions"], lang),
    }
    for k in "ABCDEFG":
        ratio = cats[k]["score"] / cats[k]["max"]
        values[f"{k}_SCORE"] = f'{cats[k]["score"]}/{cats[k]["max"]}'
        values[f"{k}_PCT"] = str(round(ratio * 100))
        values[f"{k}_BAR"] = bar_class(ratio)
    values.update({k: html.escape(v[lang]) for k, v in LABELS.items()})
    return values


def remaining(text: str) -> list[tuple[int, str]]:
    """(줄 번호, 자리) 목록. 이름 꼴이 틀린 {{…}}도 잡는다."""
    return [(i, m.group(0)) for i, line in enumerate(text.splitlines(), 1) for m in re.finditer(r"\{\{[^}\n]*\}?\}?", line)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("score_json", nargs="?", help="score.py --json 결과")
    p.add_argument("-o", "--out", help="만들 HTML 경로")
    p.add_argument("--check", metavar="HTML", help="남은 {{자리}} 검사")
    args = p.parse_args()

    if args.check:
        left = remaining(Path(args.check).read_text(encoding="utf-8"))
        for line, slot in left:
            print(f"{args.check}:{line}: {slot}")
        print(f"남은 자리 {len(left)}개" if left else "통과: 남은 자리 없음")
        return 1 if left else 0

    if not args.score_json or not args.out:
        p.error("score.json과 -o 가 필요하다 (검사는 --check)")
    out = Path(args.out).resolve()
    if out == TEMPLATE:
        print("error: 템플릿 원본에는 쓰지 않는다", file=sys.stderr)
        return 2
    values = auto_values(json.loads(Path(args.score_json).read_text(encoding="utf-8")))
    text = RE_SLOT.sub(lambda m: values.get(m.group(1), m.group(0)), TEMPLATE.read_text(encoding="utf-8"))
    out.write_text(text, encoding="utf-8")
    print(f"만듦: {args.out}")
    print("직접 쓸 자리: " + ", ".join(slot for _, slot in remaining(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
