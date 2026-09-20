"""Evidence-linked local reports and opt-in idempotent publisher contracts."""

import html
import json
from pathlib import Path

from adapters import bridge_call
from core import EvalError, digest, verify_evidence_hashes, write_json


def display(value):
    return (
        "unknown"
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
    heading = summary["verdict"] if binary else summary.get("grade", "UNSCORED")
    rows = []
    html_rows = []
    evidence_sections = []
    for r in summary["results"]:
        cid = r["case_id"]
        ev = f"evaluations/{cid}.md"
        transcript = r["evidence"]["transcript"]
        value = r["verdict"] if binary or r["score"] is None else display(r["score"])
        rows.append(
            f"| {cid} | {r['name']} | {r['category']} | {value} | [{r['verdict']}]({ev}) | [transcript]({transcript}) |"
        )
        md = f"# {cid}: {r['name']}\n\nVerdict: **{r['verdict']}**\n\n[Full transcript](../{transcript}) · [Structured evaluation]({cid}.json)\n\n"
        if r["score"] is not None:
            md += f"{'Dimension pass rate' if binary else 'Composite score'}: {display(r['score'])}\n\n"
        if r.get("error"):
            md += "Infrastructure error: " + r["error"] + "\n"
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
                    r["category"],
                    value,
                    display(r["metadata"].get("usage", {}).get("input_tokens")),
                    display(r["metadata"].get("cost_usd")),
                )
            )
            + f'<td><a href="{ev}">evaluation</a> · <a href="{transcript}">transcript</a> · <a href="#{cid}">quotes</a></td></tr>'
        )
        prompt = root / "cases" / cid / "prompt.json"
        prompt_text = prompt.read_text() if prompt.exists() else "Prompt unavailable"
        evidence_sections.append(
            f'<details id="{cid}"><summary>{cid}: prompt, checks, rubric quotes and provenance</summary><pre>'
            + html.escape(
                prompt_text + "\n" + json.dumps(r, indent=2, ensure_ascii=False)
            )
            + f'</pre><a href="{transcript}">Full transcript</a></details>'
        )
    recommendations = (
        "\n".join(
            f"- **{r['case_id']}**: {r['action']}" for r in summary["recommendations"]
        )
        or "No failing cases; repeat after relevant changes and compare against a no-skill baseline."
    )
    report = f"# Skill evaluation: {manifest['skill']['name']} — {heading}\n\nRun `{summary['run_id']}` · {summary['mode']} · {summary['grading']}\n\n"
    report += f"{summary['passed']}/{summary['total']} passed; {summary['failed']} failed; {summary['errors']} errors. Pass rate: {display(summary['pass_rate'])}.\n\n"
    report += f"Execution cost: {display(summary['execution_cost_usd'])} USD; judge cost: {display(summary['judge_cost_usd'])} USD. CLI list-price estimates, not invoices. Unknown costs are not zero.\n\n"
    report += (
        "## What this skill does\n\n"
        + manifest["skill"]["description"]
        + "\n\n## What we tested\n\n"
        + manifest["analysis"].get("purpose", "See retained analysis.json")
        + "\n\n"
    )
    report += (
        "## Results\n\n| ID | Name | Category | Score/verdict | Evaluation | Evidence |\n|---|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n"
    )
    report += (
        "## Metrics and breakdowns\n\n```json\n"
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
        "## Recommendations\n\n"
        + recommendations
        + "\n\n## Audit\n\n[Manifest](manifest.json) · [Criteria](criteria.yaml) · [Analysis](analysis.json) · [Raw summary](summary.json).\n\n"
    )
    report += "Business-impact scores are evidence-bounded rubric assessments; they do not prove causal productivity or revenue gains.\n"
    (root / "REPORT.md").write_text(report)
    if not visualize:
        return
    cards = "".join(
        f"<article><h2>{html.escape(k)}</h2><strong>{html.escape(display(v))}</strong></article>"
        for k, v in [
            ("Pass rate", summary["pass_rate"]),
            ("Cases", summary["total"]),
            ("Mode", summary["mode"]),
            ("Execution input tokens", summary["tokens"]["input_tokens"]),
            ("Case durations summed (s)", summary["duration_seconds"]),
            ("Cost (USD estimate)", summary["cost_usd"]),
        ]
    )
    charts = "".join(
        "<article><h2>"
        + html.escape(
            "Dimension pass rates"
            if binary and k == "dimensions"
            else k.replace("_", " ").title()
        )
        + "</h2><pre>"
        + html.escape(json.dumps(summary[k], indent=2))
        + "</pre></article>"
        for k in ("categories", "dimensions", "best_practice_subcriteria")
    )
    overview = "".join(
        "<article><h2>" + title + "</h2><p>" + html.escape(body) + "</p></article>"
        for title, body in [
            ("What this skill does", manifest["skill"]["description"]),
            (
                "What we tested",
                manifest["analysis"].get("purpose", "See analysis.json"),
            ),
            (
                "How it turned out",
                f"{summary['passed']} passed, {summary['failed']} failed, {summary['errors']} infrastructure errors.",
            ),
        ]
    )
    raw = html.escape(
        json.dumps(
            {"manifest": manifest, "summary": summary}, indent=2, ensure_ascii=False
        )
    )
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Skill evaluation</title><style>
:root{font-family:system-ui,sans-serif;color:#163047;background:#f1f5f8}body{max-width:1280px;margin:auto;padding:24px}h1{font-size:2.5rem}h2{font-size:1.1rem}section{margin:40px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}article,details{background:white;border:1px solid #d5dfe7;border-radius:12px;padding:20px}strong{font-size:1.6rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}th button{font:inherit;border:0;background:transparent;cursor:pointer}a{color:#0563a4}.table{overflow:auto}.badge{background:#143c55;color:white;border-radius:10px;padding:8px 16px}details{margin:10px 0}summary{cursor:pointer}@media print{button{display:none}details{break-inside:avoid}body{padding:0}}@media(max-width:500px){body{padding:12px}h1{font-size:2rem}}
</style></head><body><a href="#main">Skip to results</a><main id="main">"""
    page += f'<header><p>Auditable skill evaluation · {html.escape(summary["run_id"])}</p><h1>{html.escape(manifest["skill"]["name"])} <span class="badge">{heading}</span></h1><p>Scores link to executed evidence. Costs are estimates; business impact is not causal proof.</p></header>'
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
        "<section><h2>Recommendations</h2><pre>"
        + html.escape(recommendations)
        + '</pre></section><section class="table"><h2>Cases</h2><table id="cases"><thead><tr>'
        + "".join(
            f'<th><button onclick="sortRows({i})">{name} ↕</button></th>'
            for i, name in enumerate(
                (
                    "ID",
                    "Name",
                    "Category",
                    "Verdict" if binary else "Score",
                    "Tokens",
                    "Cost",
                    "Evidence",
                )
            )
        )
        + "</tr></thead><tbody>"
        + "".join(html_rows)
        + "</tbody></table></section>"
    )
    page += (
        "<section><h2>Evidence</h2>"
        + "".join(evidence_sections)
        + "</section><footer><details><summary>Complete raw data</summary><pre>"
        + raw
        + '</pre></details><a href="manifest.json">manifest</a> · <a href="summary.json">summary</a> · <a href="criteria.yaml">criteria</a></footer></main>'
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
            raise EvalError("Published run changed; use a new run ID")
        return prior
    bridge = config.get(kind)
    if not bridge:
        raise EvalError(
            f"{kind} requested but unavailable. Configure an authenticated bridge with verified current schema; see references/result_schema.md"
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
        raise EvalError("Publisher failed idempotency acknowledgment")
    receipt_data = {"payload_hash": payload_hash, **response}
    write_json(receipt, receipt_data)
    return receipt_data
