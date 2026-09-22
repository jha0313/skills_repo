"""근거와 연결된 로컬 보고서(Markdown, JSON, 단일 HTML 페이지)."""

import html
import json
from pathlib import Path

from core import verify_evidence_hashes, write_json

# Display labels only; stored keys and verdict enums remain unchanged.
LABELS = {
    "invocation": "호출 정확성",
    "efficiency": "효율성",
    "best_practices": "모범 사례",
    "business_impact": "업무 효과",
    "task_completion": "과제 완수",
    "context_management": "맥락 관리",
    "subagent_architecture": "하위 에이전트 구성",
    "tool_selection": "도구 선택",
    "skill_design": "스킬 설계",
    "process_adherence": "절차 준수",
    "error_handling_safety": "오류 처리·안전",
    "categories": "범주별 결과",
    "dimensions": "차원별 결과",
    "best_practice_subcriteria": "모범 사례 세부 기준",
    "count": "사례 수",
    "pass_rate": "통과율",
    "basic": "BASIC · 기본",
    "thorough": "THOROUGH · 표준",
    "deep": "DEEP · 확장",
    "binary": "Binary · 이진 판정",
    "likert": "Likert · 1–5점",
    "UNSCORED": "미채점",
}


def label(value):
    return LABELS.get(value, value)


def display_breakdown(value):
    if isinstance(value, dict):
        return {label(k): display_breakdown(v) for k, v in value.items()}
    return value


def display(value):
    return (
        "미확인"
        if value is None
        else f"{value:.3f}"
        if isinstance(value, float)
        else str(value)
    )


def write_reports(run_dir, summary, manifest, visualize=True):
    root = Path(run_dir)
    for result in summary["results"]:
        if result["status"] == "graded":
            verify_evidence_hashes(
                root, manifest["cases"][result["case_id"]].get("evidence_hashes")
            )
    write_json(root / "summary.json", summary)
    binary = summary["grading"] == "binary"
    heading = summary["verdict"] if binary else label(summary.get("grade", "UNSCORED"))
    rows = []
    html_rows = []
    evidence_sections = []
    for r in summary["results"]:
        cid = r["case_id"]
        ev = f"evaluations/{cid}.md"
        transcript = r["evidence"]["transcript"]
        value = r["verdict"] if binary or r["score"] is None else display(r["score"])
        rows.append(
            f"| {cid} | {r['name']} | {label(r['category'])} | {value} | [{r['verdict']}]({ev}) | [실행 기록]({transcript}) |"
        )
        md = f"# {cid}: {r['name']}\n\n판정: **{r['verdict']}**\n\n[전체 실행 기록](../{transcript}) · [구조화된 평가]({cid}.json)\n\n"
        if r["score"] is not None:
            md += (
                f"{'차원 통과율' if binary else '종합 점수'}: {display(r['score'])}\n\n"
            )
        if r.get("error"):
            md += "실행 환경 오류: " + r["error"] + "\n"
        md += "```json\n" + json.dumps(r, indent=2, ensure_ascii=False) + "\n```\n"
        (root / ev).parent.mkdir(exist_ok=True)
        (root / ev).write_text(md)
        write_json(root / "evaluations" / f"{cid}.json", r)
        html_rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(v))}</td>"
                for v in (
                    cid,
                    r["name"],
                    label(r["category"]),
                    value,
                    display(r["metadata"].get("usage", {}).get("input_tokens")),
                    display(r["metadata"].get("cost_usd")),
                )
            )
            + f'<td><a href="{ev}">평가</a> · <a href="{transcript}">실행 기록</a> · <a href="#{cid}">인용 근거</a></td></tr>'
        )
        prompt = root / "cases" / cid / "prompt.json"
        prompt_text = (
            prompt.read_text() if prompt.exists() else "프롬프트를 확인할 수 없습니다"
        )
        evidence_sections.append(
            f'<details id="{cid}"><summary>{cid}: 프롬프트·검사·루브릭 인용·출처</summary><pre>'
            + html.escape(
                prompt_text + "\n" + json.dumps(r, indent=2, ensure_ascii=False)
            )
            + f'</pre><a href="{transcript}">전체 실행 기록</a></details>'
        )
    recommendations = (
        "\n".join(
            f"- **{r['case_id']}**: {r['action']}" for r in summary["recommendations"]
        )
        or "실패한 사례가 없습니다. 관련 변경 후 반복 평가하고 스킬 없는 기준 실행과 비교하세요."
    )
    report = f"# 스킬 평가: {manifest['skill']['name']} — {heading}\n\n실행 `{summary['run_id']}` · {label(summary['mode'])} · {label(summary['grading'])}\n\n"
    report += f"{summary['passed']}/{summary['total']} 통과 · {summary['failed']} 실패 · {summary['errors']} 오류. 사례 통과율: {display(summary['pass_rate'])}.\n\n"
    report += f"실행 비용: {display(summary['execution_cost_usd'])} USD · 채점 비용: {display(summary['judge_cost_usd'])} USD. CLI 정가 추정치이며 청구서가 아닙니다. 미확인 비용은 0이 아닙니다.\n\n"
    report += (
        "## 이 스킬이 하는 일\n\n"
        + manifest["skill"]["description"]
        + "\n\n## 평가한 내용\n\n"
        + manifest["analysis"].get("purpose", "보존된 analysis.json을 확인하세요")
        + "\n\n"
    )
    report += (
        "## 결과\n\n| ID | 이름 | 범주 | 점수/판정 | 평가 | 근거 |\n|---|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n"
    )
    report += (
        "## 지표와 세부 결과\n\n```json\n"
        + json.dumps(
            {
                k: summary[k]
                for k in (
                    "categories",
                    "dimensions",
                    "best_practice_subcriteria",
                    "tokens",
                    "duration_seconds",
                    "failure_clusters",
                )
            },
            indent=2,
        )
        + "\n```\n\n"
    )
    report += (
        "## 개선 제안\n\n"
        + recommendations
        + "\n\n## 감사 근거\n\n[실행 명세](manifest.json) · [평가 기준](criteria.yaml) · [분석](analysis.json) · [원시 집계](summary.json).\n\n"
    )
    report += "업무 효과 점수는 근거 범위 안의 루브릭 평가이며 생산성이나 매출의 인과적 개선을 입증하지 않습니다.\n"
    (root / "REPORT.md").write_text(report)
    if not visualize:
        return
    criteria = (
        json.loads((root / "criteria.yaml").read_text())
        if (root / "criteria.yaml").exists()
        else {"test_cases": []}
    )
    (root / "REPORT.html").write_text(
        build_html(root, summary, manifest, criteria, recommendations)
    )


# ---------------------------------------------------------------------------
# Dashboard HTML report: KPI tiles → per-case scores / radar / categories / durations → insights → collapsed detail blocks
# ---------------------------------------------------------------------------

VERDICT_KO = {"PASS": "통과", "FAIL": "실패", "ERROR": "미판정"}


def esc(value):
    return html.escape("" if value is None else str(value))


def fmt(value, digits=2):
    if value is None:
        return "미확인"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def case_reason(result, spec, binary):
    """(제목, 판정 기준 문장, 목표 행동, 심판 이유 목록) for a non-passing case."""
    if result.get("status") == "error":
        return ("채점 도구 오류로 미판정", str(result.get("error", "")), "", [])
    checks = result.get("checks", {})
    for key, title in (
        ("required_present_misses", "필수 문구 누락"),
        ("forbidden_hits", "금지 문구 포함"),
        ("missing_artifacts", "필수 산출물 없음"),
        ("artifact_hash_mismatches", "보호 파일이 변경됨(sha256 불일치)"),
    ):
        if checks.get(key):
            return (
                title,
                ", ".join(checks[key]),
                "해당 파일·문구 조건을 지키도록 스킬 지침을 보강",
                [],
            )
    if checks.get("routing_failure"):
        return (
            "스킬 호출 판단 실패",
            "기대한 호출 여부와 실제 Skill 호출이 다름",
            "스킬 description의 트리거 조건을 다듬기",
            [],
        )
    specs = (spec or {}).get("quality_criteria", {}).get("semantic_checks", [])
    threshold = 1 if binary else 3
    for sem in result.get("semantic_checks", []):
        q = specs[sem["index"]] if sem["index"] < len(specs) else {}
        if q.get("critical") and sem["score"] < threshold:
            anchor = q.get("rubric", {}).get(str(sem["score"]), "")
            target = q.get("rubric", {}).get("1" if binary else "5", "")
            reasons = [
                r["semantic_checks"][sem["index"]].get("reason", "")
                for r in result.get("judge_rounds", [])
                if sem["index"] < len(r.get("semantic_checks", []))
            ]
            return (
                f"필수 검사 미달(점수 {sem['score']}): {q.get('question', '').split(chr(10))[0][:120]}",
                anchor,
                target,
                reasons,
            )
    score = result.get("score")
    return (
        "종합 점수가 통과 기준 미만",
        f"{fmt(score)} < {'1' if binary else '3.0'}",
        "",
        [],
    )


def build_insights(summary, specs, binary):
    """Plain-language findings computed from the graded results only."""
    results = summary["results"]
    items = []
    failing = [r for r in results if r["verdict"] == "FAIL"]
    errors = [r for r in results if r["verdict"] == "ERROR"]
    for r in failing:
        title, anchor, target, reasons = case_reason(r, specs.get(r["case_id"]), binary)
        body = f'<p class="k">무엇이 걸렸나</p><p>{esc(anchor)}</p>'
        if reasons:
            body += f'<p class="k">심판의 이유</p><p>{esc(reasons[0][:300])}</p>'
        if target:
            body += f'<p class="k">통과하려면</p><p>{esc(target)}</p>'
        items.append(("fail", f"{r['case_id']} {esc(r['name'])} — {esc(title)}", body))
    if not binary:
        weak = []
        for r in results:
            if r.get("status") != "graded":
                continue
            spec = specs.get(r["case_id"]) or {}
            qs = spec.get("quality_criteria", {}).get("semantic_checks", [])
            for sem in r.get("semantic_checks", []):
                if sem["score"] <= 3 and not (
                    r["verdict"] == "FAIL"
                    and qs
                    and sem["index"] < len(qs)
                    and qs[sem["index"]].get("critical")
                ):
                    q = qs[sem["index"]] if sem["index"] < len(qs) else {}
                    reason = next(
                        (
                            rr["semantic_checks"][sem["index"]].get("reason", "")
                            for rr in r.get("judge_rounds", [])
                            if sem["index"] < len(rr.get("semantic_checks", []))
                        ),
                        "",
                    )
                    weak.append(
                        (
                            sem["score"],
                            r["case_id"],
                            q.get("question", f"질문 {sem['index']}").split("\n")[0][
                                :110
                            ],
                            reason[:220],
                        )
                    )
        weak.sort()
        for score, cid, question, reason in weak[:3]:
            items.append(
                (
                    "weak",
                    f"{cid} — {score}점 항목: {esc(question)}",
                    f"<p>{esc(reason)}</p>",
                )
            )
        low_cases = [
            r
            for r in results
            if r.get("status") == "graded"
            and r["verdict"] == "PASS"
            and (r.get("score") or 5) < 3.5
        ]
        for r in low_cases:
            dims_r = r.get("dimensions", {})
            worst = min(dims_r.items(), key=lambda kv: kv[1]) if dims_r else None
            note = (
                f" 가장 낮은 관점은 {esc(label(worst[0]))} {fmt(worst[1], 1)}점."
                if worst
                else ""
            )
            timed = (
                " 시간 초과로 그때까지 한 일만 채점됐습니다."
                if r["metadata"].get("timed_out")
                else ""
            )
            items.append(
                (
                    "weak",
                    f"{r['case_id']} {esc(r['name'])} — 통과했지만 {fmt(r.get('score'))}점으로 낮음",
                    f"<p>통과 기준(3.0)은 넘었지만 여유가 적습니다.{note}{timed}</p>",
                )
            )
        dims = summary.get("dimensions", {})
        if dims:
            low = min(dims.items(), key=lambda kv: (kv[1] is None, kv[1]))
            if low[1] is not None and low[1] < 4:
                d = low[0]
                scored = [
                    r
                    for r in results
                    if r.get("status") == "graded" and d in r.get("dimensions", {})
                ]
                body = ""
                if scored:
                    worst_case = min(scored, key=lambda r: r["dimensions"][d])
                    reason = next(
                        (
                            rr["dimensions"][d].get("reason", "")
                            for rr in worst_case.get("judge_rounds", [])
                            if d in rr.get("dimensions", {})
                        ),
                        "",
                    )
                    body = f"<p>가장 낮은 문제: {esc(worst_case['case_id'])} {fmt(worst_case['dimensions'][d], 1)}점.</p>"
                    if reason:
                        body += (
                            f'<p class="k">심판의 이유</p><p>{esc(reason[:300])}</p>'
                        )
                if d == "business_impact":
                    body += "<p>업무 효과는 작은 연습 문제에서 상한이 낮은 관점이라 그 자체를 결함으로 보지는 않습니다.</p>"
                items.append(
                    ("weak", f"가장 낮은 관점: {esc(label(d))} {fmt(low[1])}점", body)
                )
    graded = [r for r in results if r.get("status") == "graded"]
    slow = sorted(graded, key=lambda r: -(r["metadata"].get("duration_seconds") or 0))[
        :2
    ]
    timed = [r["case_id"] for r in results if r["metadata"].get("timed_out")]
    if slow:
        parts = ", ".join(
            f"{r['case_id']} {r['metadata'].get('duration_seconds') or 0:.0f}초"
            for r in slow
        )
        body = f"<p>가장 오래 걸린 문제: {esc(parts)}.</p>"
        if timed:
            body += f"<p>시간 초과: {esc(', '.join(timed))}. 시간 초과 문제는 그때까지 한 일만 채점됩니다.</p>"
        items.append(("info", "실행 시간", body))
    for r in errors:
        items.append(
            (
                "error",
                f"{r['case_id']} {esc(r['name'])} — 미판정",
                f"<p>{esc(str(r.get('error', ''))[:300])}</p><p>스킬의 실패가 아니라 채점 도구 문제입니다. <code>--resume</code>으로 다시 채점할 수 있습니다.</p>",
            )
        )
    if not failing and not errors:
        items.insert(
            0,
            (
                "ok",
                "결함이 발견되지 않았습니다",
                "<p>모든 문제가 통과했습니다. 아래 '낮은 항목'은 통과했지만 점수가 낮은 곳이며, 스킬 지침을 다듬을 후보입니다.</p>",
            ),
        )
    return items


def radar_svg(dims, binary):
    """Inline SVG radar of dimension values (1–5 Likert or 0–1 binary rate)."""
    import math

    keys = [k for k in dims]
    n = len(keys)
    if n < 3:
        return ""
    cx = cy = 130
    r = 88

    def pt(i, frac):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * frac * math.cos(a), cy + r * frac * math.sin(a)

    grid = "".join(
        '<polygon points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lv) for i in range(n)))
        + f'" fill="none" stroke="#e4e2dc" stroke-width="{1.4 if lv == 1 else 0.8}"/>'
        for lv in (0.25, 0.5, 0.75, 1)
    )
    axes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{pt(i, 1)[0]:.1f}" y2="{pt(i, 1)[1]:.1f}" stroke="#e4e2dc" stroke-width=".8"/>'
        for i in range(n)
    )
    vals = []
    for i, k in enumerate(keys):
        v = dims[k]
        frac = 0 if v is None else (v if binary else (v - 1) / 4)
        vals.append((pt(i, max(0, min(1, frac))), v))
    poly = (
        '<polygon points="'
        + " ".join(f"{x:.1f},{y:.1f}" for (x, y), _ in vals)
        + '" fill="rgba(42,120,214,.22)" stroke="#2a78d6" stroke-width="2"/>'
    )
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#2a78d6"/>'
        for (x, y), _ in vals
    )
    labels = ""
    for i, k in enumerate(keys):
        x, y = pt(i, 1.24)
        anchor = "middle" if abs(x - cx) < 12 else ("start" if x > cx else "end")
        v = dims[k]
        val = "미확인" if v is None else (f"{v:.0%}" if binary else f"{v:.2f}")
        labels += f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="11" fill="#52514e"><tspan font-weight="700" fill="#0b0b0b">{esc(label(k))}</tspan> {val}</text>'
    return f'<svg viewBox="-52 -8 364 276" role="img" aria-label="차원별 점수 레이더">{grid}{axes}{poly}{dots}{labels}</svg>'


def build_html(root, summary, manifest, criteria, recommendations):
    binary = summary["grading"] == "binary"
    specs = {c["id"]: c for c in criteria.get("test_cases", [])}
    results = summary["results"]
    skill = manifest["skill"]["name"]
    options = manifest.get("options", {})
    total, passed = summary["total"], summary["passed"]
    tone = (
        "good"
        if summary["verdict"] == "PASS"
        else ("critical" if summary["failed"] else "warning")
    )
    cost = summary.get("cost_usd")
    minutes = (summary.get("wall_clock_seconds") or 0) / 60
    rounds = options.get("judge_rounds", "?")
    cond = f"{label(summary['mode'])} · {label(summary['grading'])} · 채점 {rounds}회 · 모델 {esc(options.get('model') or 'CLI 기본')}"

    # ---- KPI tiles ----
    fails = summary["failed"]
    errs = summary["errors"]
    sub_pass = (
        " · ".join(
            s
            for s in (
                f"실패 {fails}" if fails else "",
                f"미판정 {errs}" if errs else "",
            )
            if s
        )
        or "전부 통과"
    )
    tiles = [
        (tone, f"{passed}/{total}", "통과", sub_pass),
    ]
    if binary:
        tiles.append(
            (
                tone,
                "PASS" if summary["verdict"] == "PASS" else "FAIL",
                "판정",
                f"통과율 {summary['pass_rate']:.0%}"
                if summary.get("pass_rate") is not None
                else "",
            )
        )
    else:
        tiles.append(
            (
                "",
                summary.get("grade") or "-",
                "등급",
                f"평균 {fmt(summary.get('score'))} / 5"
                if summary.get("score") is not None
                else "채점된 문제 없음",
            )
        )
    tiles.append(
        (
            "",
            f"${cost:.2f}" if cost is not None else "미확인",
            "비용(추정)",
            f"실행 {fmt(summary.get('execution_cost_usd'))} · 채점 {fmt(summary.get('judge_cost_usd'))}",
        )
    )
    slowest = max(
        (r for r in results if r["metadata"].get("duration_seconds")),
        key=lambda r: r["metadata"]["duration_seconds"],
        default=None,
    )
    tiles.append(
        (
            "",
            f"{minutes:.0f}분" if minutes else "미확인",
            "소요 시간",
            f"가장 긴 문제 {slowest['case_id']} {slowest['metadata']['duration_seconds']:.0f}초"
            if slowest
            else "",
        )
    )
    tile_html = "".join(
        f'<div class="tile"><div class="v {t}">{esc(v)}</div><div class="l">{esc(name)}</div><div class="s">{esc(s)}</div></div>'
        for t, v, name, s in tiles
    )

    # ---- per-case score bars ----
    case_rows = []
    for r in results:
        v = r["verdict"]
        cid = r["case_id"]
        score = r.get("score")
        if score is None:
            width, txt = 0, "미판정"
        elif binary:
            width, txt = score * 100, f"{score:.0%}"
        else:
            width, txt = (score - 1) / 4 * 100, fmt(score)
        case_rows.append(
            f'<a class="crow v-{esc(v)}" href="#case-{esc(cid)}" title="{esc(r["name"])}"><span class="cid"><i class="dot"></i>{esc(cid)}</span><span class="cname">{esc(r["name"])}</span>'
            f'<span class="bar"><i style="width:{max(0, min(100, width)):.0f}%"></i></span><span class="cval">{esc(txt)}</span></a>'
        )
    thr = "통과선 1.0(모든 차원)" if binary else "통과선 3.0"

    # ---- category + duration panels ----
    cat_rows = []
    for c, info in summary.get("categories", {}).items():
        rate = info.get("pass_rate")
        cnt = info.get("count", 0)
        ok = round((rate or 0) * cnt)
        cat_rows.append(
            f'<div class="mrow"><span class="ml">{esc(label(c))}</span><span class="bar"><i style="width:{(rate or 0) * 100:.0f}%"></i></span><span class="mv">{ok}/{cnt}</span></div>'
        )
    durs = [
        (
            r["case_id"],
            r["metadata"].get("duration_seconds") or 0,
            r["metadata"].get("timed_out"),
        )
        for r in results
    ]
    dmax = max([d for _, d, _ in durs] + [1])
    dur_rows = "".join(
        f'<div class="mrow"><span class="ml">{esc(cid)}</span><span class="bar"><i class="{"to" if to else ""}" style="width:{d / dmax * 100:.0f}%"></i></span><span class="mv">{d:.0f}초{" ⚠" if to else ""}</span></div>'
        for cid, d, to in durs
    )
    dur_note = (
        "⚠ 시간 초과: 그때까지 한 일만 채점" if any(to for _, _, to in durs) else ""
    )

    # ---- insights ----
    insight_html = "".join(
        f'<details class="insight {kind}"><summary>{title}</summary><div class="ibody">{body}</div></details>'
        for kind, title, body in build_insights(summary, specs, binary)
    )

    # ---- how it was tested ----
    tested = []
    for r in results:
        cid = r["case_id"]
        spec = specs.get(cid) or {}
        prompt_file = root / "cases" / cid / "prompt.json"
        prompt = spec.get("prompt")
        if not prompt and prompt_file.exists():
            try:
                prompt = json.loads(prompt_file.read_text()).get("prompt", "")
            except ValueError:
                prompt = prompt_file.read_text()
        expected = spec.get("expected_behavior")
        body = (f'<p class="prompt">{esc(prompt)}</p>' if prompt else "") + (
            f'<p class="expect"><b>기대한 행동</b> {esc(expected)}</p>'
            if expected
            else ""
        )
        tested.append(
            f'<details class="tcase"><summary><span class="tid">{esc(cid)}</span><span class="cat">{esc(label(r["category"]))}</span>{esc(r["name"])}</summary>{body}</details>'
        )
    method = (
        f"문제마다 스킬이 설치된 격리 세션에서 실행하고, 실행 기록만 보는 별도의 심판 세션 {rounds}개가 근거를 인용해 채점합니다. "
        "필수 검사가 하나라도 실패하면 점수와 관계없이 실패입니다."
    )

    # ---- per-case details (collapsed) ----
    details = []
    for r in results:
        cid = r["case_id"]
        spec = specs.get(cid) or {}
        qs = spec.get("quality_criteria", {}).get("semantic_checks", [])
        rows = []
        for sem in r.get("semantic_checks", []):
            q = qs[sem["index"]] if sem["index"] < len(qs) else {}
            reasons = "".join(
                f"<li>심판 {i}: {rr['semantic_checks'][sem['index']].get('score')}점 — {esc(rr['semantic_checks'][sem['index']].get('reason', ''))}</li>"
                for i, rr in enumerate(r.get("judge_rounds", []), 1)
                if sem["index"] < len(rr.get("semantic_checks", []))
            )
            anchor = q.get("rubric", {}).get(str(sem["score"]), "")
            crit_tag = ' <span class="crit">필수</span>' if q.get("critical") else ""
            rows.append(
                f'<tr><td class="score s-{sem["score"]}">{sem["score"]}{"" if binary else "/5"}</td>'
                f'<td><div class="q">{esc(q.get("question", "질문 " + str(sem["index"])))}{crit_tag}</div>'
                + (
                    f'<div class="anchor">판정 기준: {esc(anchor)}</div>'
                    if anchor
                    else ""
                )
                + (
                    f"<details><summary>심판 이유</summary><ul>{reasons}</ul></details>"
                    if reasons
                    else ""
                )
                + "</td></tr>"
            )
        checks = r.get("checks", {})
        det = []
        for key, name in (
            ("required_present_hits", "필수 문구 확인"),
            ("required_present_misses", "필수 문구 누락"),
            ("forbidden_hits", "금지 문구 포함"),
            ("missing_artifacts", "산출물 없음"),
            ("artifact_hash_mismatches", "보호 파일 변경"),
        ):
            if checks.get(key):
                det.append(f"{name}: {', '.join(checks[key])}")
        if checks.get("routing_failure"):
            det.append("스킬 호출 판단 실패")
        dims = r.get("dimensions", {})
        dim_cells = " · ".join(
            f"{esc(label(k))} {fmt(v, 1) if not binary else ('통과' if v else '실패')}"
            for k, v in dims.items()
        )
        md = r.get("metadata", {})
        meta = f"{md.get('duration_seconds') or 0:.0f}초 · 토큰 {fmt(md.get('usage', {}).get('input_tokens'))}/{fmt(md.get('usage', {}).get('output_tokens'))} · 비용 {fmt(md.get('cost_usd'))}"
        if md.get("timed_out"):
            meta += " · 시간 초과"
        links = [
            ("평가 상세", f"evaluations/{cid}.md"),
            ("전체 실행 기록", r["evidence"]["transcript"]),
            ("최종 응답", f"cases/{cid}/response.txt"),
            ("도구 호출", f"cases/{cid}/tool_calls.json"),
            ("산출물", f"cases/{cid}/artifacts/"),
        ]
        link_html = " · ".join(
            f'<a href="{esc(p)}">{n}</a>'
            for n, p in links
            if (root / p).exists() or n in ("평가 상세", "전체 실행 기록")
        )
        v = r["verdict"]
        body = ""
        if r.get("status") == "error":
            body += f'<p class="err">채점 도구 오류: {esc(r.get("error"))}</p>'
        if v != "PASS" and r.get("status") == "graded":
            title, anchor, target, _ = case_reason(r, spec, binary)
            body += f'<p class="why"><b>실패 이유</b> {esc(title)}. {esc(anchor)}</p>'
        if spec.get("prompt") or spec.get("expected_behavior"):
            body += (
                "<details><summary>프롬프트와 기대한 행동</summary>"
                + (
                    f'<p class="prompt">{esc(spec["prompt"])}</p>'
                    if spec.get("prompt")
                    else ""
                )
                + (
                    f'<p class="expect"><b>기대한 행동</b> {esc(spec["expected_behavior"])}</p>'
                    if spec.get("expected_behavior")
                    else ""
                )
                + "</details>"
            )
        if dim_cells:
            body += f'<p class="dims">{dim_cells}</p>'
        if rows:
            body += f'<table class="qs"><thead><tr><th>점수</th><th>검사 질문</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
        if det:
            body += f'<p class="det">결정적 검사: {esc("; ".join(det))}</p>'
        body += f'<p class="meta">{esc(meta)}</p><p class="links">{link_html}</p>'
        details.append(
            f'<details class="case v-{esc(v)}" id="case-{esc(cid)}">'
            f'<summary><i class="dot"></i>{esc(cid)} {esc(r["name"])} <span class="badge">{esc(VERDICT_KO.get(v, v))}{"" if binary or r.get("score") is None else " " + fmt(r.get("score"))}</span></summary>{body}</details>'
        )

    raw = esc(
        json.dumps(
            {"manifest": manifest, "summary": summary}, indent=2, ensure_ascii=False
        )
    )
    dim_title = "차원별 통과율" if binary else "다섯 관점 (1~5)"
    style = """
:root{color-scheme:light;--bg:#f4f4f1;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7873;--line:#e4e2dc;--accent:#2a78d6;--good:#0ca30c;--warn:#e4a11b;--bad:#d03b3b;font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);background:var(--bg);line-height:1.5}
body{max-width:1120px;margin:auto;padding:26px 20px 60px}h1{font-size:1.5rem;margin:0;letter-spacing:-.02em}h2{font-size:.82rem;font-weight:700;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin:0 0 10px}h3{font-size:1rem;margin:0 0 6px}p{margin:6px 0}.sub{color:var(--ink2);font-size:.9rem}a{color:#0563a4}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;margin-bottom:16px}header .run{color:var(--muted);font-size:.8rem}header .cond{margin-left:auto;color:var(--ink2);font-size:.85rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:12px}.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}.tile .v{font-size:1.9rem;font-weight:800;letter-spacing:-.03em;line-height:1.1}.tile .v.good{color:var(--good)}.tile .v.critical{color:var(--bad)}.tile .v.warning{color:#8a4b00}.tile .l{font-size:.8rem;font-weight:700;color:var(--muted);margin-top:2px}.tile .s{font-size:.78rem;color:var(--ink2);margin-top:2px}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;align-items:start}.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;min-width:0}.col{display:grid;gap:12px;min-width:0}.c7{grid-column:span 7}.c5{grid-column:span 5}.c12{grid-column:span 12}.note{font-size:.76rem;color:var(--muted);margin:8px 0 0}
.crow{display:grid;grid-template-columns:78px minmax(0,150px) 1fr 52px;align-items:center;gap:8px;padding:4px 0;text-decoration:none;color:inherit;font-size:.85rem;border-radius:6px}.crow:hover{background:#f6f5f2}.cid{font-weight:700;display:flex;align-items:center;gap:6px;color:var(--ink2)}.cname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink2)}.cval{text-align:right;font-weight:700}
.bar{position:relative;height:9px;background:#eeece7;border-radius:5px;overflow:hidden;display:block}.bar i{display:block;height:100%;background:var(--accent);border-radius:5px}.crow .bar::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;border-left:2px dashed #b9b6ae}.v-FAIL .bar i{background:var(--bad)}.v-ERROR .bar i{background:var(--warn)}.v-PASS .bar i{background:var(--good)}.bar i.to{background:var(--warn)}
.dot{width:10px;height:10px;border-radius:50%;background:#ccc;display:inline-block;flex:none}.v-PASS .dot{background:var(--good)}.v-FAIL .dot{background:var(--bad)}.v-ERROR .dot{background:var(--warn)}
.mrow{display:grid;grid-template-columns:96px 1fr 64px;align-items:center;gap:8px;font-size:.84rem;padding:3px 0}.ml{color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mv{text-align:right;color:var(--ink2)}
.radar{display:flex;justify-content:center}.radar svg{width:100%;max-width:340px;height:auto}
details{border-radius:12px}summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px}summary::-webkit-details-marker{display:none}summary::before{content:"";width:7px;height:7px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(-45deg);transition:transform .15s;flex:none;margin:0 4px}details[open]>summary::before{transform:rotate(45deg)}
.igrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:10px}.insight{background:#fbfaf8;border:1px solid var(--line);border-left:5px solid var(--accent);padding:10px 14px;align-self:start}.insight>summary{font-weight:600;font-size:.9rem}.insight.fail{border-left-color:var(--bad)}.insight.error{border-left-color:var(--warn)}.insight.ok{border-left-color:var(--good)}.insight.weak{border-left-color:#ec835a}.insight.info{border-left-color:#b9b6ae}.ibody{padding:6px 0 4px 19px;font-size:.88rem}.insight .k{font-size:.74rem;font-weight:700;color:var(--muted);margin:8px 0 0;letter-spacing:.04em}
details.block{background:var(--card);border:1px solid var(--line);padding:14px 18px;margin:12px 0}details.block>summary{font-size:1.05rem;font-weight:700}details.block>summary .hint{margin-left:auto;font-size:.8rem;font-weight:500;color:var(--muted)}details.block>summary h2{margin:0;font-size:inherit;color:inherit;letter-spacing:0;text-transform:none}.block-body{padding-top:10px}
.tcase{border-top:1px solid var(--line);padding:8px 0;border-radius:0}.tcase>summary{font-size:.9rem;font-weight:600}.tid{font-size:.76rem;font-weight:700;color:var(--muted);letter-spacing:.04em}.cat{font-size:.74rem;font-weight:600;background:#eef3fb;color:var(--accent);border-radius:999px;padding:1px 8px}.prompt{white-space:pre-wrap;color:var(--ink2);font-size:.88rem;background:#f6f5f2;border-radius:8px;padding:10px;margin:8px 0 4px 19px}.expect{font-size:.88rem;color:var(--ink2);margin-left:19px}
details.case{border:1px solid var(--line);padding:10px 14px;margin:8px 0}details.case>summary{font-weight:600}details.case.v-FAIL{border-color:#f1bcbc}details.case.v-ERROR{border-color:#f3dc9a}.badge{margin-left:auto;font-size:.8rem;font-weight:600;background:#f1f0ec;border-radius:999px;padding:2px 10px}.v-FAIL .badge{background:#fbe9e9;color:var(--bad)}.v-PASS .badge{background:#e8f6e8;color:#006300}.v-ERROR .badge{background:#fff4d6;color:#6d4a00}
.why{background:#fdf3f0;border-radius:8px;padding:8px 12px}.err{background:#fff4d6;border-radius:8px;padding:8px 12px}.dims{font-size:.86rem;color:var(--ink2)}table.qs{width:100%;border-collapse:collapse;margin:8px 0;font-size:.88rem}table.qs th,table.qs td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}table.qs th{white-space:nowrap;color:var(--ink2);font-size:.8rem}.score{font-weight:800;white-space:nowrap}.s-1,.s-2{color:var(--bad)}.s-3{color:#8a4b00}.q{font-weight:600}.crit{font-size:.72rem;font-weight:700;color:var(--bad);background:#fbe9e9;border-radius:999px;padding:1px 6px;margin-left:6px}.anchor{color:var(--ink2);font-size:.84rem}.det,.meta{font-size:.82rem;color:var(--ink2)}.links a{margin-right:8px}
.filters{margin-bottom:8px}.filters button{font:inherit;font-size:.84rem;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:5px 12px;cursor:pointer;margin-right:6px}.filters button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
footer{color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:14px;margin-top:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.74rem}
@media(max-width:760px){body{padding:16px 12px}.c7,.c5{grid-column:span 12}.crow{grid-template-columns:70px 1fr 48px}.cname{display:none}header .cond{margin-left:0}}
"""
    script = """
document.querySelectorAll(".filters button").forEach(function(b){b.addEventListener("click",function(){document.querySelectorAll(".filters button").forEach(function(x){x.classList.remove("on")});b.classList.add("on");var f=b.dataset.f;document.querySelectorAll("details.case").forEach(function(d){d.style.display=(f==="all"||d.classList.contains("v-"+f))?"":"none"})})});
function reveal(){var t=location.hash&&document.getElementById(location.hash.slice(1));if(!t)return;for(var e=t;e;e=e.parentElement){if(e.tagName==="DETAILS")e.open=true}t.scrollIntoView()}
window.addEventListener("hashchange",reveal);reveal();
"""
    page = (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(skill)} 스킬 평가</title><style>{style}</style></head><body><main id="main">'
        f'<header><h1>{esc(skill)}</h1><span class="run">스킬 평가 · {esc(summary["run_id"])}</span><span class="cond">{cond}</span></header>'
        f'<section class="tiles">{tile_html}</section>'
        f'<section class="grid">'
        f'<div class="col c7"><div class="panel"><h2>문제별 점수</h2>{"".join(case_rows)}<p class="note">초록 통과 · 빨강 실패 · 노랑 미판정(채점 도구 문제) · 점선은 {thr} · 누르면 상세로</p></div>'
        f'<div class="panel"><h2>실행 시간</h2>{dur_rows}<p class="note">{esc(dur_note)}</p></div></div>'
        f'<div class="col c5"><div class="panel"><h2>{esc(dim_title)}</h2><div class="radar">{radar_svg(summary.get("dimensions", {}), binary)}</div></div>'
        f'<div class="panel"><h2>범주별 통과</h2>{"".join(cat_rows)}</div></div>'
        f'<div class="panel c12"><h2>인사이트</h2><div class="igrid">{insight_html}</div></div>'
        f"</section>"
        f'<details class="block" id="tested"><summary><h2>어떻게 시험했나</h2><span class="hint">{total}문제</span></summary><div class="block-body">'
        f'<p class="sub">{esc(method)}</p><p class="sub">{esc(manifest.get("analysis", {}).get("purpose", ""))}</p>{"".join(tested)}</div></details>'
        f'<details class="block" id="cases"><summary><h2>문제별 상세</h2><span class="hint">점수·심판 이유·근거 링크</span></summary><div class="block-body">'
        f'<div class="filters"><button class="on" data-f="all">전체</button><button data-f="FAIL">실패만</button><button data-f="ERROR">미판정만</button></div>{"".join(details)}</div></details>'
        f"<footer><details><summary>원시 데이터</summary><pre>{raw}</pre></details>"
        f'<p><a href="REPORT.md">REPORT.md</a> · <a href="manifest.json">실행 명세</a> · <a href="summary.json">집계</a> · <a href="criteria.yaml">평가 기준</a> · 비용은 CLI 정가 추정치. 업무 효과 점수는 루브릭 판단이며 인과적 효과의 증명이 아닙니다.</p></footer></main>'
        f"<script>{script}</script></body></html>"
    )
    return page
