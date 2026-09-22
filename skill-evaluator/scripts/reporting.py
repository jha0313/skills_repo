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
# Readable HTML report: what was tested → results at a glance → insights → details
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


def build_html(root, summary, manifest, criteria, recommendations):
    binary = summary["grading"] == "binary"
    specs = {c["id"]: c for c in criteria.get("test_cases", [])}
    results = summary["results"]
    skill = manifest["skill"]["name"]
    options = manifest.get("options", {})
    total, passed = summary["total"], summary["passed"]
    verdict_word = (
        "전부 통과"
        if summary["verdict"] == "PASS"
        else ("일부 실패" if summary["failed"] else "미판정 있음")
    )
    tone = (
        "good"
        if summary["verdict"] == "PASS"
        else ("critical" if summary["failed"] else "warning")
    )
    head = f"{total}문제 중 {passed}개 통과"
    if summary.get("grade") and not binary:
        head += f", 등급 {summary['grade']}"
    cost = summary.get("cost_usd")
    minutes = (summary.get("wall_clock_seconds") or 0) / 60
    cond = f"{label(summary['mode'])} · {label(summary['grading'])} · 채점 {options.get('judge_rounds', '?')}회 · 모델 {esc(options.get('model') or 'CLI 기본')}"
    cond += f" · 비용 약 ${cost:.2f}(추정)" if cost is not None else " · 비용 미확인"
    cond += f" · {minutes:.0f}분" if minutes else ""

    # ---- what was tested ----
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
        short = (prompt or "").replace("\n", " ")
        short = short[:150] + ("…" if len(short) > 150 else "")
        expected = spec.get("expected_behavior")
        detail = (
            f'<details><summary>프롬프트 전문과 기대한 행동</summary><p class="prompt">{esc(prompt)}</p>'
            + (
                f'<p class="expect"><b>기대한 행동</b> {esc(expected)}</p>'
                if expected
                else ""
            )
            + "</details>"
            if prompt
            else ""
        )
        tested.append(
            f'<article class="tcase"><div class="tid">{esc(cid)} <span class="cat">{esc(label(r["category"]))}</span></div>'
            f"<h3>{esc(r['name'])}</h3>"
            + (f'<p class="expect">{esc(short)}</p>' if short else "")
            + detail
            + "</article>"
        )

    # ---- results at a glance ----
    dots = []
    for r in results:
        v = r["verdict"]
        score = (
            (r["verdict"] if binary else fmt(r.get("score")))
            if r.get("score") is not None
            else "-"
        )
        dots.append(
            f'<a class="dot-card v-{esc(v)}" href="#case-{esc(r["case_id"])}"><span class="dot"></span>'
            f'<span class="dot-id">{esc(r["case_id"])}</span><span class="dot-name">{esc(r["name"])}</span>'
            f'<span class="dot-score">{esc(VERDICT_KO.get(v, v))}{"" if binary or r.get("score") is None else " · " + score}</span></a>'
        )
    bars = []
    for d, v in summary.get("dimensions", {}).items():
        if v is None:
            bars.append(
                f'<div class="bar-row"><span class="bar-label">{esc(label(d))}</span><span class="bar-val">미확인</span></div>'
            )
            continue
        width = (v * 100) if binary else ((v - 1) / 4 * 100)
        bars.append(
            f'<div class="bar-row"><span class="bar-label">{esc(label(d))}</span><span class="bar"><i style="width:{max(0, min(100, width)):.0f}%"></i></span>'
            f'<span class="bar-val">{fmt(v)}{"" if binary else " / 5"}</span></div>'
        )
    dim_title = "차원별 통과율" if binary else "다섯 관점의 평균 점수 (1~5)"

    # ---- insights ----
    insights = build_insights(summary, specs, binary)
    insight_html = "".join(
        f'<article class="insight {kind}"><h3>{title}</h3>{body}</article>'
        for kind, title, body in insights
    )

    # ---- per-case details ----
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
        if spec.get("prompt"):
            body += f'<details><summary>시킨 것(프롬프트)</summary><p class="prompt">{esc(spec["prompt"])}</p></details>'
        if spec.get("expected_behavior"):
            body += f"<p><b>기대한 행동</b> {esc(spec['expected_behavior'])}</p>"
        if dim_cells:
            body += f'<p class="dims">{dim_cells}</p>'
        if rows:
            body += f'<table class="qs"><thead><tr><th>점수</th><th>검사 질문</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
        if det:
            body += f'<p class="det">결정적 검사: {esc("; ".join(det))}</p>'
        body += f'<p class="meta">{esc(meta)}</p><p class="links">{link_html}</p>'
        details.append(
            f'<details class="case v-{esc(v)}" id="case-{esc(cid)}"{" open" if v != "PASS" else ""}>'
            f'<summary><span class="dot"></span>{esc(cid)} {esc(r["name"])} <span class="badge">{esc(VERDICT_KO.get(v, v))}{"" if binary or r.get("score") is None else " " + fmt(r.get("score"))}</span></summary>{body}</details>'
        )

    raw = esc(
        json.dumps(
            {"manifest": manifest, "summary": summary}, indent=2, ensure_ascii=False
        )
    )
    style = """
:root{color-scheme:light;--bg:#fcfcfb;--card:#fff;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7873;--line:#e4e2dc;--accent:#2a78d6;--good:#0ca30c;--warn:#fab219;--bad:#d03b3b;font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);background:var(--bg);line-height:1.6}
body{max-width:1060px;margin:auto;padding:32px 20px 60px}h1{font-size:1.9rem;margin:0 0 4px;letter-spacing:-.02em}h2{font-size:1.3rem;margin:0 0 12px}h3{font-size:1.02rem;margin:0 0 6px}section{margin:34px 0}p{margin:6px 0}.sub{color:var(--ink2)}
.hero{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 26px;margin:18px 0}.hero .big{font-size:2rem;font-weight:800;letter-spacing:-.03em}.hero .big.good{color:var(--good)}.hero .big.critical{color:var(--bad)}.hero .big.warning{color:#8a4b00}.hero .cond{color:var(--ink2);font-size:.92rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}.tcase{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}.tid{font-size:.78rem;font-weight:700;color:var(--muted);letter-spacing:.04em}.cat{font-weight:600;background:#eef3fb;color:var(--accent);border-radius:999px;padding:1px 8px;margin-left:6px}.prompt{white-space:pre-wrap;color:var(--ink2);font-size:.92rem;background:#f6f5f2;border-radius:8px;padding:10px}.expect{font-size:.92rem;color:var(--ink2)}
.dot-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}.dot-card{display:grid;grid-template-columns:16px 1fr;gap:4px 10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;text-decoration:none;color:inherit}.dot-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.08)}.dot{width:14px;height:14px;border-radius:50%;background:#ccc;display:inline-block}.v-PASS .dot{background:var(--good)}.v-FAIL .dot{background:var(--bad)}.v-ERROR .dot{background:var(--warn)}.dot-card.v-FAIL{background:#fdf5f3;border-color:#f1bcbc}.dot-card.v-ERROR{background:#fff8e6;border-color:#f3dc9a}.dot-id{font-size:.75rem;font-weight:700;color:var(--muted)}.dot-name{grid-column:2;font-size:.92rem;font-weight:600;line-height:1.35}.dot-score{grid-column:2;font-size:.82rem;color:var(--ink2)}
.bars{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-top:14px}.bar-row{display:grid;grid-template-columns:120px 1fr 70px;align-items:center;gap:10px;margin:6px 0;font-size:.92rem}.bar{height:10px;background:#eeece7;border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}.bar-val{text-align:right;color:var(--ink2)}
.insight{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:12px;padding:14px 18px;margin:10px 0}.insight.fail{border-left-color:var(--bad)}.insight.error{border-left-color:var(--warn)}.insight.ok{border-left-color:var(--good)}.insight.weak{border-left-color:#ec835a}.insight .k{font-size:.78rem;font-weight:700;color:var(--muted);margin:8px 0 0;letter-spacing:.04em}
details.case{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:10px 0}details.case>summary{cursor:pointer;font-weight:600;display:flex;align-items:center;gap:8px}details.case.v-FAIL{border-color:#f1bcbc}details.case.v-ERROR{border-color:#f3dc9a}.badge{margin-left:auto;font-size:.8rem;font-weight:600;background:#f1f0ec;border-radius:999px;padding:2px 10px}.v-FAIL .badge{background:#fbe9e9;color:var(--bad)}.v-PASS .badge{background:#e8f6e8;color:#006300}.v-ERROR .badge{background:#fff4d6;color:#6d4a00}
.why{background:#fdf3f0;border-radius:8px;padding:8px 12px}.err{background:#fff4d6;border-radius:8px;padding:8px 12px}.dims{font-size:.88rem;color:var(--ink2)}table.qs{width:100%;border-collapse:collapse;margin:8px 0;font-size:.92rem}table.qs th,table.qs td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}table.qs th{white-space:nowrap;color:var(--ink2);font-size:.82rem}.score{font-weight:800;white-space:nowrap}.s-1,.s-2{color:var(--bad)}.s-3{color:#8a4b00}.q{font-weight:600}.crit{font-size:.72rem;font-weight:700;color:var(--bad);background:#fbe9e9;border-radius:999px;padding:1px 6px;margin-left:6px}.anchor{color:var(--ink2);font-size:.88rem}.det,.meta{font-size:.85rem;color:var(--ink2)}.links a{margin-right:8px}a{color:#0563a4}
.filters button{font:inherit;font-size:.88rem;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:6px 12px;cursor:pointer;margin-right:6px}.filters button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
footer{color:var(--muted);font-size:.85rem;border-top:1px solid var(--line);padding-top:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.78rem}
@media(max-width:600px){body{padding:18px 12px}.bar-row{grid-template-columns:90px 1fr 60px}}
"""
    page = (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(skill)} 스킬 평가</title><style>{style}</style></head><body>'
        f'<a href="#glance">결과로 바로가기</a><main id="main">'
        f'<header><p class="sub">스킬 평가 보고 · {esc(summary["run_id"])}</p><h1>{esc(skill)}</h1>'
        f'<div class="hero"><div class="big {tone}">{esc(head)} — {esc(verdict_word)}</div><p class="cond">{cond}</p>'
        f"<p>{esc(manifest['skill'].get('description', ''))}</p></div></header>"
        f'<section id="glance"><h2>결과 한눈에</h2><p class="sub">초록 통과 · 빨강 실패 · 노랑 미판정(채점 도구 문제). 카드를 누르면 상세로 이동합니다.</p><div class="dot-grid">{"".join(dots)}</div>'
        f'<div class="bars"><h3>{esc(dim_title)}</h3>{"".join(bars)}</div></section>'
        f'<section id="insights"><h2>개선 인사이트</h2><p class="sub">채점 결과에서 자동으로 뽑은 것입니다. 실패 이유와 통과하려면 무엇이 필요한지, 통과했더라도 낮은 항목을 보여 줍니다.</p>{insight_html}</section>'
        f'<section id="tested"><h2>무엇을 시험했나</h2><p class="sub">{esc(manifest.get("analysis", {}).get("purpose", ""))}</p><div class="grid">{"".join(tested)}</div></section>'
        f'<section id="cases"><h2>문제별 상세</h2><div class="filters"><button class="on" data-f="all">전체</button><button data-f="FAIL">실패만</button><button data-f="ERROR">미판정만</button></div>{"".join(details)}</section>'
        f"<footer><details><summary>원시 데이터(원문 유지)</summary><pre>{raw}</pre></details>"
        f'<p><a href="REPORT.md">REPORT.md</a> · <a href="manifest.json">실행 명세</a> · <a href="summary.json">집계</a> · <a href="criteria.yaml">평가 기준</a> · 비용은 CLI 정가 추정치이며 청구서가 아닙니다. 업무 효과 점수는 루브릭 판단이며 인과적 효과의 증명이 아닙니다.</p></footer></main>'
        '<script>document.querySelectorAll(".filters button").forEach(function(b){b.addEventListener("click",function(){document.querySelectorAll(".filters button").forEach(function(x){x.classList.remove("on")});b.classList.add("on");var f=b.dataset.f;document.querySelectorAll("details.case").forEach(function(d){d.style.display=(f==="all"||d.classList.contains("v-"+f))?"":"none"})})});</script></body></html>'
    )
    return page
