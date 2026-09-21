"""근거와 연결된 로컬 보고서 및 명시적 선택에 따른 멱등 발행 계약."""

import html
import json
from pathlib import Path

from adapters import bridge_call
from core import EvalError, digest, verify_evidence_hashes, write_json

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
    cards = "".join(
        f"<article><h2>{html.escape(k)}</h2><strong>{html.escape(display(v))}</strong></article>"
        for k, v in [
            ("사례 통과율", summary["pass_rate"]),
            ("사례 수", summary["total"]),
            ("모드", label(summary["mode"])),
            ("대상 실행 입력 토큰", summary["tokens"]["input_tokens"]),
            ("사례별 소요 시간 합계(초)", summary["duration_seconds"]),
            ("비용(USD 추정)", summary["cost_usd"]),
        ]
    )
    charts = "".join(
        "<article><h2>"
        + html.escape("차원별 통과율" if binary and k == "dimensions" else label(k))
        + "</h2><pre>"
        + html.escape(
            json.dumps(display_breakdown(summary[k]), indent=2, ensure_ascii=False)
        )
        + "</pre></article>"
        for k in ("categories", "dimensions", "best_practice_subcriteria")
    )
    overview = "".join(
        "<article><h2>" + title + "</h2><p>" + html.escape(body) + "</p></article>"
        for title, body in [
            ("이 스킬이 하는 일", manifest["skill"]["description"]),
            (
                "평가한 내용",
                manifest["analysis"].get("purpose", "analysis.json을 확인하세요"),
            ),
            (
                "평가 결과",
                f"통과 {summary['passed']}개, 실패 {summary['failed']}개, 실행 환경 오류 {summary['errors']}개.",
            ),
        ]
    )
    raw = html.escape(
        json.dumps(
            {"manifest": manifest, "summary": summary}, indent=2, ensure_ascii=False
        )
    )
    page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>스킬 평가</title><style>
:root{font-family:system-ui,sans-serif;color:#163047;background:#f1f5f8}body{max-width:1280px;margin:auto;padding:24px}h1{font-size:2.5rem}h2{font-size:1.1rem}section{margin:40px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}article,details{background:white;border:1px solid #d5dfe7;border-radius:12px;padding:20px}strong{font-size:1.6rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}th button{font:inherit;border:0;background:transparent;cursor:pointer}a{color:#0563a4}.table{overflow:auto}.badge{background:#143c55;color:white;border-radius:10px;padding:8px 16px}details{margin:10px 0}summary{cursor:pointer}@media print{button{display:none}details{break-inside:avoid}body{padding:0}}@media(max-width:500px){body{padding:12px}h1{font-size:2rem}}
</style></head><body><a href="#main">결과로 바로가기</a><main id="main">"""
    page += f'<header><p>근거를 확인할 수 있는 스킬 평가 · {html.escape(summary["run_id"])}</p><h1>{html.escape(manifest["skill"]["name"])} <span class="badge">{heading}</span></h1><p>점수에서 실제 실행 근거를 확인할 수 있습니다. 비용은 추정치이며 업무 효과 점수는 인과관계의 증명이 아닙니다.</p></header>'
    page += (
        '<section class="grid">'
        + cards
        + '</section><section class="grid">'
        + overview
        + '</section><section class="grid">'
        + charts
        + "</section>"
    )
    page += (
        "<section><h2>개선 제안</h2><pre>"
        + html.escape(recommendations)
        + '</pre></section><section class="table"><h2>사례</h2><table id="cases"><thead><tr>'
        + "".join(
            f'<th><button onclick="sortRows({i})">{name} ↕</button></th>'
            for i, name in enumerate(
                (
                    "ID",
                    "이름",
                    "범주",
                    "판정" if binary else "점수",
                    "토큰",
                    "비용",
                    "근거",
                )
            )
        )
        + "</tr></thead><tbody>"
        + "".join(html_rows)
        + "</tbody></table></section>"
    )
    page += (
        "<section><h2>근거</h2>"
        + "".join(evidence_sections)
        + "</section><footer><details><summary>전체 원시 데이터(원문 유지)</summary><pre>"
        + raw
        + '</pre></details><a href="manifest.json">실행 명세</a> · <a href="summary.json">집계</a> · <a href="criteria.yaml">평가 기준</a></footer></main>'
    )
    page += """<script>function sortRows(n){var b=document.querySelector('#cases tbody');Array.from(b.rows).sort(function(a,c){return a.cells[n].textContent.localeCompare(c.cells[n].textContent,undefined,{numeric:true})}).forEach(function(r){b.appendChild(r)})}</script></body></html>"""
    (root / "REPORT.html").write_text(page)


def publish(run_dir, summary, config, kind, create_project=False):
    root = Path(run_dir)
    receipt = root / f"{kind}-receipt.json"
    key = summary["run_id"]
    payload_hash = digest(summary)
    if receipt.exists():
        prior = json.loads(receipt.read_text())
        if prior["payload_hash"] != payload_hash:
            raise EvalError("발행한 실행의 내용이 바뀌었습니다. 새 run ID를 사용하세요")
        return prior
    bridge = config.get(kind)
    if not bridge:
        raise EvalError(
            f"{kind}를 요청했지만 사용할 수 없습니다. 현재 스키마가 확인된 인증 bridge를 설정하세요. references/result_schema.md를 참고하세요"
        )
    response = bridge_call(
        bridge,
        "publish",
        {
            "run_id": key,
            "idempotency_key": key,
            "create_project": create_project,
            "summary": summary,
            "report_path": str(root / "REPORT.html"),
        },
        root / f"{kind}-publication",
    )
    if response.get("idempotency_key") != key:
        raise EvalError("발행 시스템이 멱등성 확인을 반환하지 않았습니다")
    receipt_data = {"payload_hash": payload_hash, **response}
    write_json(receipt, receipt_data)
    return receipt_data
