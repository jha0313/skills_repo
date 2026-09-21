"""Before/after comparison dashboard for two canonical skill-evaluator runs.

Reporting only: reads summary.json / manifest.json / criteria.yaml / evaluations of two
finished runs and writes one self-contained HTML next to them. Never re-grades or edits runs.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path

DIMS = (
    "invocation",
    "efficiency",
    "best_practices",
    "business_impact",
    "task_completion",
)
LABEL = {
    "invocation": "invocation",
    "efficiency": "efficiency",
    "best_practices": "best practices",
    "business_impact": "business impact",
    "task_completion": "task completion",
}


def load(run):
    run = Path(run).expanduser().resolve()
    summary = json.loads((run / "summary.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    criteria = json.loads((run / "criteria.yaml").read_text())
    return run, summary, manifest, criteria


def fmt(v, digits=2):
    if v is None:
        return "unknown"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def delta(a, b, digits=2):
    if a is None or b is None:
        return "–"
    d = b - a
    sign = "+" if d > 0 else ""
    cls = "up" if d > 0 else "down" if d < 0 else "flat"
    return f'<span class="{cls}">{sign}{d:.{digits}f}</span>'


def rel(out_dir, run, path):
    return html.escape(os.path.relpath(run / path, out_dir))


def failing_evidence(run, out_dir, result, criteria_case):
    """Concrete, linkable reasons a case did not PASS."""
    items = []
    if result.get("status") == "error":
        items.append(("infrastructure error", html.escape(str(result.get("error")))))
        return items
    checks = result.get("checks", {})
    for key, label in (
        ("required_present_misses", "required text missing"),
        ("forbidden_hits", "forbidden text present"),
        ("missing_artifacts", "required artifact missing"),
        ("artifact_hash_mismatches", "protected artifact changed (sha256 mismatch)"),
    ):
        if checks.get(key):
            items.append(
                (label, html.escape(json.dumps(checks[key], ensure_ascii=False)))
            )
    if checks.get("routing_failure"):
        items.append(
            ("routing", "expected invocation state not observed in Skill calls")
        )
    specs = criteria_case["quality_criteria"]["semantic_checks"]
    for sem in result.get("semantic_checks", []):
        spec = specs[sem["index"]]
        if spec.get("critical") and sem["score"] < 3:
            reasons = []
            for rn, round_ in enumerate(result.get("judge_rounds", []), 1):
                j = round_["semantic_checks"][sem["index"]]
                ev = j.get("evidence", [{}])[0]
                reasons.append(
                    f"<li>round {rn}: score {j['score']} — {html.escape(j.get('reason', ''))}"
                    f'<br><a href="{rel(out_dir, run, ev.get("path", ""))}">{html.escape(ev.get("path", ""))}:{ev.get("line_start")}-{ev.get("line_end")}</a> '
                    f"<code>{html.escape(str(ev.get('quote', ''))[:200])}</code></li>"
                )
            items.append(
                (
                    f"critical check q{sem['index']} voted {sem['score']} (<3)",
                    f"<div>{html.escape(spec['question'])}</div><ul>{''.join(reasons)}</ul>",
                )
            )
    if not items and result.get("verdict") != "PASS":
        items.append(
            ("composite below threshold", f"score {fmt(result.get('score'))} < 3.0")
        )
    return items


def case_links(run, out_dir, cid):
    parts = [
        ("evaluation", f"evaluations/{cid}.md"),
        ("response", f"cases/{cid}/response.txt"),
        ("tool calls", f"cases/{cid}/tool_calls.json"),
        ("metadata", f"cases/{cid}/metadata.json"),
        ("transcript", f"cases/{cid}/conversation.txt"),
    ]
    if (run / "cases" / cid / "artifacts").is_dir():
        parts.append(("artifacts", f"cases/{cid}/artifacts/"))
    return " · ".join(
        f'<a href="{rel(out_dir, run, p)}">{n}</a>'
        for n, p in parts
        if (run / p).exists()
    )


def build(before, after, out, label_a, label_b):
    ra, sa, ma, ca = load(before)
    rb, sb, mb, cb = load(after)
    out = Path(out).expanduser().resolve()
    out_dir = out.parent
    if ma["criteria_hash"] != mb["criteria_hash"]:
        raise SystemExit(
            "criteria hashes differ; paired comparison is not interpretable (same rule as `compare`)"
        )
    env_rows = []
    for key, va, vb in (
        ("criteria_hash", ma["criteria_hash"], mb["criteria_hash"]),
        ("evaluator_hash", ma["evaluator_hash"], mb["evaluator_hash"]),
        (
            "target skill_hash (expected to differ)",
            ma["skill"]["skill_hash"],
            mb["skill"]["skill_hash"],
        ),
        ("target revision", ma["skill"]["revision"], mb["skill"]["revision"]),
        (
            "model / judge_model",
            f"{ma['options'].get('model')} / {ma['options'].get('judge_model')}",
            f"{mb['options'].get('model')} / {mb['options'].get('judge_model')}",
        ),
        (
            "allow_tools",
            ",".join(ma["options"].get("allow_tools", [])),
            ",".join(mb["options"].get("allow_tools", [])),
        ),
        (
            "judge_rounds / concurrency",
            f"{ma['options']['judge_rounds']} / {ma['options']['concurrency']}",
            f"{mb['options']['judge_rounds']} / {mb['options']['concurrency']}",
        ),
        (
            "claude CLI",
            ma["dependencies"].get("claude_version"),
            mb["dependencies"].get("claude_version"),
        ),
    ):
        same = va == vb
        env_rows.append(
            f'<tr class="{"same" if same else "diff"}"><td>{html.escape(key)}</td><td><code>{html.escape(str(va))}</code></td><td><code>{html.escape(str(vb))}</code></td><td>{"same" if same else "DIFFERENT"}</td></tr>'
        )
    cards = "".join(
        f"<article><h2>{html.escape(k)}</h2><p><strong>{fmt(a)}</strong> → <strong>{fmt(b)}</strong> {d}</p></article>"
        for k, a, b, d in (
            (
                "Pass rate (cases)",
                sa["pass_rate"],
                sb["pass_rate"],
                delta(sa["pass_rate"], sb["pass_rate"]),
            ),
            (
                "Passed / total",
                f"{sa['passed']}/{sa['total']}",
                f"{sb['passed']}/{sb['total']}",
                "",
            ),
            (
                "Failed · errors",
                f"{sa['failed']} · {sa['errors']}",
                f"{sb['failed']} · {sb['errors']}",
                "",
            ),
            (
                "Mean composite (Likert)",
                sa.get("score"),
                sb.get("score"),
                delta(sa.get("score"), sb.get("score")),
            ),
            (
                "Suite verdict",
                sa["verdict"] + (f" ({sa.get('grade')})" if sa.get("grade") else ""),
                sb["verdict"] + (f" ({sb.get('grade')})" if sb.get("grade") else ""),
                "",
            ),
            (
                "Cost USD (execution+judge, estimate)",
                sa.get("execution_and_judge_cost_usd"),
                sb.get("execution_and_judge_cost_usd"),
                delta(
                    sa.get("execution_and_judge_cost_usd"),
                    sb.get("execution_and_judge_cost_usd"),
                ),
            ),
            (
                "Wall clock s",
                sa.get("wall_clock_seconds"),
                sb.get("wall_clock_seconds"),
                delta(sa.get("wall_clock_seconds"), sb.get("wall_clock_seconds"), 0),
            ),
        )
    )
    cat_rows = "".join(
        f"<tr><td>{LABEL[d]}</td><td>{fmt(sa['categories'][d]['pass_rate'])} ({sa['categories'][d]['count']})</td><td>{fmt(sb['categories'][d]['pass_rate'])} ({sb['categories'][d]['count']})</td><td>{delta(sa['categories'][d]['pass_rate'], sb['categories'][d]['pass_rate'])}</td>"
        f"<td>{fmt(sa['dimensions'].get(d))}</td><td>{fmt(sb['dimensions'].get(d))}</td><td>{delta(sa['dimensions'].get(d), sb['dimensions'].get(d))}</td></tr>"
        for d in DIMS
    )
    bp_rows = "".join(
        f"<tr><td>{k}</td><td>{fmt(sa['best_practice_subcriteria'].get(k))}</td><td>{fmt(sb['best_practice_subcriteria'].get(k))}</td><td>{delta(sa['best_practice_subcriteria'].get(k), sb['best_practice_subcriteria'].get(k))}</td></tr>"
        for k in sa["best_practice_subcriteria"]
    )
    res_a = {r["case_id"]: r for r in sa["results"]}
    res_b = {r["case_id"]: r for r in sb["results"]}
    spec = {c["id"]: c for c in ca["test_cases"]}
    case_rows, evidence = [], []
    for cid in sorted(res_a):
        a, b = res_a[cid], res_b.get(cid, {})
        change = "same" if a["verdict"] == b.get("verdict") else "changed"
        case_rows.append(
            f'<tr class="{change}"><td><a href="#{cid}">{cid}</a></td><td>{html.escape(a["name"])}</td><td>{LABEL.get(a["category"], a["category"])}</td>'
            f'<td class="v-{a["verdict"]}">{a["verdict"]} {fmt(a.get("score"))}{" ⚠crit" if a.get("critical_failure") else ""}</td>'
            f'<td class="v-{b.get("verdict")}">{b.get("verdict")} {fmt(b.get("score"))}{" ⚠crit" if b.get("critical_failure") else ""}</td>'
            f"<td>{delta(a.get('score'), b.get('score'))}</td><td>{case_links(ra, out_dir, cid)}</td><td>{case_links(rb, out_dir, cid)}</td></tr>"
        )
        blocks = []
        for tag, run, r in ((label_a, ra, a), (label_b, rb, b)):
            if r and r.get("verdict") != "PASS":
                items = failing_evidence(run, out_dir, r, spec[cid])
                blocks.append(
                    f"<h4>{html.escape(tag)}: {r.get('verdict')}</h4><dl>"
                    + "".join(
                        f"<dt>{html.escape(k)}</dt><dd>{v}</dd>" for k, v in items
                    )
                    + "</dl>"
                )
        if blocks:
            evidence.append(
                f'<details id="{cid}" open><summary>{cid} — {html.escape(a["name"])}</summary>{"".join(blocks)}</details>'
            )
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Before/After: {html.escape(ma["skill"]["name"])}</title><style>
:root{{font-family:system-ui,sans-serif;color:#163047;background:#f1f5f8}}body{{max-width:1320px;margin:auto;padding:24px}}h1{{font-size:2rem}}h2{{font-size:1.05rem}}section{{margin:32px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}article,details{{background:#fff;border:1px solid #d5dfe7;border-radius:12px;padding:16px}}strong{{font-size:1.3rem}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #ddd;vertical-align:top}}.table{{overflow:auto}}.up{{color:#137333;font-weight:600}}.down{{color:#b3261e;font-weight:600}}.flat{{color:#666}}.v-PASS{{color:#137333}}.v-FAIL{{color:#b3261e}}.v-ERROR{{color:#8a4b00}}tr.changed{{background:#fff8e1}}tr.diff{{background:#fdecea}}code{{font-size:.8rem;overflow-wrap:anywhere}}dt{{font-weight:600;margin-top:8px}}dd{{margin:2px 0 6px 12px}}a{{color:#0563a4}}@media(max-width:600px){{body{{padding:12px}}}}
</style></head><body><main>
<header><p>skill-evaluator paired comparison · observational, same criteria/model/harness</p><h1>{html.escape(ma["skill"]["name"])}: {html.escape(label_a)} → {html.escape(label_b)}</h1>
<p>{html.escape(label_a)} = <code>{html.escape(sa["run_id"])}</code> · {html.escape(label_b)} = <code>{html.escape(sb["run_id"])}</code>. 점수는 3명의 독립 judge 중앙값 기반 composite이며, critical 실패(⚠crit)는 composite와 무관하게 FAIL입니다. 인과적 개선이나 측정된 생산성 이득을 주장하지 않습니다.</p></header>
<section class="grid">{cards}</section>
<section class="table"><h2>환경 대조 (paired run 조건)</h2><table><thead><tr><th>항목</th><th>{html.escape(label_a)}</th><th>{html.escape(label_b)}</th><th>동일?</th></tr></thead><tbody>{"".join(env_rows)}</tbody></table></section>
<section class="table"><h2>Category pass rate · Dimension 평균</h2><table><thead><tr><th>dimension</th><th>pass rate {html.escape(label_a)} (n)</th><th>pass rate {html.escape(label_b)} (n)</th><th>Δ</th><th>dim mean {html.escape(label_a)}</th><th>dim mean {html.escape(label_b)}</th><th>Δ</th></tr></thead><tbody>{cat_rows}</tbody></table></section>
<section class="table"><h2>Best-practice subcriteria (mean of voted scores)</h2><table><thead><tr><th>subcriterion</th><th>{html.escape(label_a)}</th><th>{html.escape(label_b)}</th><th>Δ</th></tr></thead><tbody>{bp_rows}</tbody></table></section>
<section class="table"><h2>Case별 결과 (변경된 verdict는 노란 행)</h2><table><thead><tr><th>ID</th><th>name</th><th>category</th><th>{html.escape(label_a)}</th><th>{html.escape(label_b)}</th><th>Δ score</th><th>evidence {html.escape(label_a)}</th><th>evidence {html.escape(label_b)}</th></tr></thead><tbody>{"".join(case_rows)}</tbody></table></section>
<section><h2>실패 근거 (PASS가 아닌 case만)</h2>{"".join(evidence) or "<p>모든 case가 두 run에서 PASS.</p>"}</section>
<footer><p>원본 보고서: <a href="{rel(out_dir, ra, "REPORT.html")}">{html.escape(label_a)} REPORT.html</a> · <a href="{rel(out_dir, rb, "REPORT.html")}">{html.escape(label_b)} REPORT.html</a> · <a href="{rel(out_dir, ra, "manifest.json")}">manifest A</a> · <a href="{rel(out_dir, rb, "manifest.json")}">manifest B</a></p></footer>
</main></body></html>"""
    out.write_text(page)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label-a", default="before")
    ap.add_argument("--label-b", default="after")
    args = ap.parse_args()
    print(build(args.before, args.after, args.out, args.label_a, args.label_b))
