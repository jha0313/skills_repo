"""Paired before/after dashboard for two canonical skill-evaluator runs.

Reporting only: reads summary.json / manifest.json / criteria.yaml / cases/*/metadata.json
of two finished runs and writes one self-contained HTML next to them. It never
re-grades or edits a run. Optional analyst notes (Markdown) are rendered verbatim in
their own section so computed insights and human interpretation stay separate.
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
DIM_KO = {
    "invocation": "호출 판단",
    "efficiency": "효율",
    "best_practices": "모범 사례",
    "business_impact": "실용성",
    "task_completion": "작업 완수",
}
CAT_KO = {**DIM_KO}


def load(run):
    run = Path(run).expanduser().resolve()
    summary = json.loads((run / "summary.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    criteria = json.loads((run / "criteria.yaml").read_text())
    return run, summary, manifest, criteria


def esc(v):
    return html.escape(str(v))


def fmt(v, digits=2):
    if v is None:
        return "알 수 없음"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def delta_html(a, b, digits=2, up_is_good=True, unit=""):
    if a is None or b is None:
        return '<span class="delta flat">–</span>'
    d = b - a
    if abs(d) < 10 ** (-digits) / 2:
        return '<span class="delta flat">변화 없음</span>'
    good = (d > 0) == up_is_good
    sign = "+" if d > 0 else "−"
    return f'<span class="delta {"good" if good else "bad"}">{sign}{abs(d):.{digits}f}{unit}</span>'


def rel(out_dir, run, path):
    return esc(os.path.relpath(run / path, out_dir))


def case_meta(run, cid):
    md = json.loads((run / "cases" / cid / "metadata.json").read_text())
    stats = md.get("subagent_stats") or {}
    agents = stats.get("spawned")
    if agents is None:
        calls = json.loads((run / "cases" / cid / "tool_calls.json").read_text())
        agents = sum(
            1 for c in calls if c.get("name") == "Agent" and c.get("actor") == "parent"
        )
    return {
        "agents": agents,
        "duration": md.get("duration_seconds"),
        "cost": md.get("cost_usd"),
        "exit": md.get("exit_state"),
        "timed_out": md.get("timed_out"),
    }


def status_of(before, after):
    a, b = before.get("verdict"), after.get("verdict")
    if a != "PASS" and b == "PASS":
        return "improved", "✓ 개선 (FAIL → PASS)", "good"
    if a == "PASS" and b != "PASS":
        return "regressed", "✕ 악화 (PASS → FAIL)", "critical"
    if b == "PASS":
        return "same-pass", "통과 유지", "neutral"
    if b == "ERROR":
        return "error", "⚠ 인프라 오류", "warning"
    return "same-fail", "✕ 여전히 실패", "serious"


def failing_reasons(run, out_dir, result, spec):
    """Korean rubric anchors at the voted score for critical misses, plus deterministic failures."""
    items = []
    if result.get("status") == "error":
        items.append(("인프라 오류", esc(result.get("error"))))
        return items
    checks = result.get("checks", {})
    labels = {
        "required_present_misses": "필수 문구 누락",
        "forbidden_hits": "금지 문구 포함",
        "missing_artifacts": "필수 산출물 없음",
        "artifact_hash_mismatches": "보호 파일이 변경됨 (sha256 불일치)",
    }
    for key, label in labels.items():
        if checks.get(key):
            items.append((label, esc(", ".join(checks[key]))))
    if checks.get("routing_failure"):
        items.append(
            ("스킬 호출 판단 실패", "기대한 호출 여부와 실제 Skill 호출이 다름")
        )
    specs = spec["quality_criteria"]["semantic_checks"]
    for sem in result.get("semantic_checks", []):
        q = specs[sem["index"]]
        if q.get("critical") and sem["score"] < 3:
            anchor = q["rubric"].get(str(sem["score"]), "")
            rounds = "".join(
                f"<li>judge {i}: {j['score']}점 — {esc(j.get('reason', ''))}</li>"
                for i, j in enumerate(
                    (
                        r["semantic_checks"][sem["index"]]
                        for r in result.get("judge_rounds", [])
                    ),
                    1,
                )
            )
            items.append(
                (
                    f"필수 검사 q{sem['index']} 미달 (중앙값 {sem['score']}점, 3점 미만이면 실패)",
                    f'<p class="q">{esc(q["question"].split(" 이 항목은")[0])}</p>'
                    f"<p><b>판정 앵커 ({sem['score']}점):</b> {esc(anchor)}</p>"
                    f"<details><summary>judge 3명의 이유 (영문 원문)</summary><ul>{rounds}</ul></details>",
                )
            )
    if not items and result.get("verdict") != "PASS":
        items.append(("종합 점수 미달", f"composite {fmt(result.get('score'))} < 3.0"))
    return items


def case_links(run, out_dir, cid):
    parts = [
        ("판정 상세", f"evaluations/{cid}.md"),
        ("최종 응답", f"cases/{cid}/response.txt"),
        ("도구 호출 기록", f"cases/{cid}/tool_calls.json"),
        ("산출물", f"cases/{cid}/artifacts/"),
    ]
    return " · ".join(
        f'<a href="{rel(out_dir, run, p)}">{n}</a>'
        for n, p in parts
        if (run / p).exists()
    )


def notes_html(text):
    out = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        body = line[2:] if line.startswith(("- ", "* ")) else line
        # minimal markdown: **bold**
        parts = body.split("**")
        rendered = "".join(
            (f"<b>{esc(p)}</b>" if i % 2 else esc(p)) for i, p in enumerate(parts)
        )
        if line.startswith("## "):
            out.append(f"<h3>{esc(line[3:])}</h3>")
        elif line.startswith(("- ", "* ")):
            out.append(f"<li>{rendered}</li>")
        else:
            out.append(f"<p>{rendered}</p>")
    joined = "\n".join(out)
    return joined.replace("<li>", "<ul><li>", 1).replace(
        "</li>\n<p>", "</li></ul>\n<p>"
    ) + ("</ul>" if joined.rstrip().endswith("</li>") else "")


def build(before, after, out, label_a="before", label_b="after", notes=None):
    ra, sa, ma, ca = load(before)
    rb, sb, mb, cb = load(after)
    out = Path(out).expanduser().resolve()
    out_dir = out.parent
    if ma["criteria_hash"] != mb["criteria_hash"]:
        raise SystemExit(
            "criteria hashes differ; paired comparison is not interpretable"
        )
    spec = {c["id"]: c for c in ca["test_cases"]}
    res_a = {r["case_id"]: r for r in sa["results"]}
    res_b = {r["case_id"]: r for r in sb["results"]}
    skill = ma["skill"]["name"]
    ver_a = ma["skill"].get("revision", "")[:8]
    ver_b = mb["skill"].get("revision", "")[:8]

    # ---- computed insights -------------------------------------------------
    improved, regressed, still_failing = [], [], []
    for cid in sorted(res_a):
        kind, _, _ = status_of(res_a[cid], res_b.get(cid, {}))
        name = spec[cid]["name"]
        if kind == "improved":
            improved.append((cid, name))
        elif kind == "regressed":
            regressed.append((cid, name))
        elif kind in ("same-fail", "error"):
            still_failing.append((cid, name))
    exec_cases = [
        cid for cid in sorted(spec) if spec[cid].get("working_directory", ".") != "."
    ]
    meta_a = {cid: case_meta(ra, cid) for cid in sorted(spec)}
    meta_b = {cid: case_meta(rb, cid) for cid in sorted(spec)}
    agents_a = sum(meta_a[c]["agents"] or 0 for c in exec_cases)
    agents_b = sum(meta_b[c]["agents"] or 0 for c in exec_cases)
    dur_a = sum(meta_a[c]["duration"] or 0 for c in exec_cases)
    dur_b = sum(meta_b[c]["duration"] or 0 for c in exec_cases)
    dim_moves = [
        (d, sa["dimensions"].get(d), sb["dimensions"].get(d))
        for d in DIMS
        if sa["dimensions"].get(d) is not None
        and sb["dimensions"].get(d) is not None
        and abs(sb["dimensions"][d] - sa["dimensions"][d]) >= 0.1
    ]
    retries_a = (
        len(list((ra / "judges").glob("*-retry-*"))) if (ra / "judges").exists() else 0
    )
    retries_b = (
        len(list((rb / "judges").glob("*-retry-*"))) if (rb / "judges").exists() else 0
    )

    insights = []
    insights.append(
        f"<li><b>통과 case {sa['passed']} → {sb['passed']} (10개 중).</b> "
        + (
            "개선: " + ", ".join(f"{c} {esc(n)}" for c, n in improved) + ". "
            if improved
            else "개선된 case 없음. "
        )
        + (
            "악화: " + ", ".join(f"{c} {esc(n)}" for c, n in regressed) + ". "
            if regressed
            else ""
        )
        + (
            "여전히 실패: " + ", ".join(f"{c} {esc(n)}" for c, n in still_failing) + "."
            if still_failing
            else "실패 case 없음."
        )
        + "</li>"
    )
    for cid, name in still_failing:
        reasons = failing_reasons(rb, out_dir, res_b[cid], spec[cid])
        heads = "; ".join(esc(h) for h, _ in reasons)
        insights.append(
            f"<li><b>{cid} {esc(name)}은(는) 개선 후에도 실패.</b> 이유: {heads}. "
            f'<a href="#{cid}">근거 보기</a></li>'
        )
    if exec_cases:
        insights.append(
            f"<li><b>실행형 case {len(exec_cases)}개의 worker 수 합계 {agents_a} → {agents_b}, "
            f"실행 시간 합계 {dur_a:.0f}초 → {dur_b:.0f}초.</b> 각 case는 한 번씩만 실행했으므로 "
            f"방향만 참고하고 크기는 변동 범위 안일 수 있다.</li>"
        )
    if dim_moves:
        insights.append(
            "<li><b>0.1 이상 움직인 차원:</b> "
            + ", ".join(f"{DIM_KO[d]} {a:.2f} → {b:.2f}" for d, a, b in dim_moves)
            + ". 나머지 차원은 사실상 동일.</li>"
        )
    else:
        insights.append(
            "<li><b>차원 평균은 모두 0.1 미만으로 움직였다.</b> 점수 차이보다 통과/실패의 이유를 보라.</li>"
        )
    insights.append(
        f"<li><b>비용·시간:</b> 실행+judge 비용 {fmt(sa.get('execution_and_judge_cost_usd'))} → "
        f"{fmt(sb.get('execution_and_judge_cost_usd'))} USD(CLI 추정), 전체 소요 "
        f"{(sa.get('wall_clock_seconds') or 0) / 60:.0f}분 → {(sb.get('wall_clock_seconds') or 0) / 60:.0f}분. "
        f"judge 재시도 {retries_a}회 → {retries_b}회(재시도된 라운드는 새 세션으로 다시 채점됨).</li>"
    )
    insights.append(
        "<li><b>신뢰도:</b> 같은 기준·harness·모델·옵션에서 스킬만 바꾼 관찰 비교다. "
        "judge 3명의 중앙값은 변동을 줄이지만 편향을 없애지 않으며, 한 번의 before/after로 인과를 주장하지 않는다.</li>"
    )

    # ---- verdict line -------------------------------------------------------
    verdict = (
        f"{skill} {esc(label_a)}({ver_a}) → {esc(label_b)}({ver_b}): 통과 {sa['passed']}/{sa['total']} → {sb['passed']}/{sb['total']}. "
        + (f"{len(improved)}건 개선" if improved else "개선 없음")
        + (f", {len(regressed)}건 악화" if regressed else "")
        + (
            f", {len(still_failing)}건은 여전히 실패."
            if still_failing
            else ", 실패 없음."
        )
    )

    # ---- stat tiles ----------------------------------------------------------
    tiles = []
    for label, a, b, digits, up_good, unit in (
        ("통과 case 수", sa["passed"], sb["passed"], 0, True, ""),
        ("통과율", sa["pass_rate"], sb["pass_rate"], 2, True, ""),
        ("평균 composite (1~5)", sa.get("score"), sb.get("score"), 2, True, ""),
        (
            "실행 비용 (USD 추정)",
            sa.get("execution_cost_usd"),
            sb.get("execution_cost_usd"),
            2,
            False,
            "",
        ),
        (
            "judge 비용 (USD 추정)",
            sa.get("judge_cost_usd"),
            sb.get("judge_cost_usd"),
            2,
            False,
            "",
        ),
        (
            "전체 소요 (분)",
            (sa.get("wall_clock_seconds") or 0) / 60,
            (sb.get("wall_clock_seconds") or 0) / 60,
            0,
            False,
            "분",
        ),
    ):
        tiles.append(
            f'<article class="tile"><div class="label">{esc(label)}</div>'
            f'<div class="value"><span class="before">{fmt(a, digits)}</span><span class="arrow">→</span><span class="after">{fmt(b, digits)}</span></div>'
            f"{delta_html(a, b, digits, up_good, unit)}</article>"
        )

    # ---- dimension paired bars ---------------------------------------------
    bars = []
    for d in DIMS:
        a, b = sa["dimensions"].get(d), sb["dimensions"].get(d)
        if a is None or b is None:
            continue
        bars.append(
            f'<div class="dim"><div class="dim-label">{DIM_KO[d]}<span class="muted"> ({d})</span></div>'
            f'<div class="bar-row"><span class="bar before" style="width:{(a - 1) / 4 * 100:.1f}%"></span><span class="bar-val">{a:.2f}</span></div>'
            f'<div class="bar-row"><span class="bar after" style="width:{(b - 1) / 4 * 100:.1f}%"></span><span class="bar-val">{b:.2f} {delta_html(a, b)}</span></div></div>'
        )

    # ---- case table ------------------------------------------------------------
    rows, details = [], []
    for cid in sorted(res_a):
        a, b = res_a[cid], res_b.get(cid, {})
        kind, label, tone = status_of(a, b)
        ma_, mb_ = meta_a[cid], meta_b[cid]
        effort = (
            f"worker {ma_['agents']} → {mb_['agents']}, {ma_['duration'] or 0:.0f}s → {mb_['duration'] or 0:.0f}s"
            if cid in exec_cases
            else "지식 문답"
        )
        rows.append(
            f'<tr class="{kind}"><td><a href="#{cid}">{cid}</a></td><td><b>{esc(spec[cid]["name"])}</b><div class="muted small">{esc(spec[cid]["description"])}</div></td>'
            f"<td>{CAT_KO.get(a['category'], a['category'])}</td>"
            f'<td class="v-{a["verdict"]}">{a["verdict"]} {fmt(a.get("score"))}</td>'
            f'<td class="v-{b.get("verdict")}">{b.get("verdict")} {fmt(b.get("score"))}</td>'
            f'<td><span class="badge {tone}">{label}</span></td><td class="small">{effort}</td></tr>'
        )
        blocks = []
        for tag, run, r in ((label_a, ra, a), (label_b, rb, b)):
            if r and r.get("verdict") != "PASS":
                items = failing_reasons(run, out_dir, r, spec[cid])
                blocks.append(
                    f"<h4>{esc(tag)}: {r.get('verdict')} (composite {fmt(r.get('score'))})</h4><dl>"
                    + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items)
                    + "</dl>"
                )
        if blocks:
            details.append(
                f'<details id="{cid}" open><summary>{cid} — {esc(spec[cid]["name"])} <span class="badge {tone}">{label}</span></summary>'
                f'<p class="muted small">프롬프트: {esc(spec[cid]["prompt"])}</p>'
                + "".join(blocks)
                + f'<p class="small">근거 {esc(label_a)}: {case_links(ra, out_dir, cid)}<br>근거 {esc(label_b)}: {case_links(rb, out_dir, cid)}</p></details>'
            )
        else:
            details.append(
                f'<details id="{cid}"><summary>{cid} — {esc(spec[cid]["name"])} <span class="badge {tone}">{label}</span></summary>'
                f'<p class="muted small">프롬프트: {esc(spec[cid]["prompt"])}</p>'
                f'<p class="small">근거 {esc(label_a)}: {case_links(ra, out_dir, cid)}<br>근거 {esc(label_b)}: {case_links(rb, out_dir, cid)}</p></details>'
            )

    # ---- environment fingerprint ------------------------------------------------
    env_rows = []
    for key, va, vb in (
        ("평가 기준 hash", ma["criteria_hash"], mb["criteria_hash"]),
        ("evaluator(harness) hash", ma["evaluator_hash"], mb["evaluator_hash"]),
        (
            "대상 스킬 hash (달라야 정상)",
            ma["skill"]["skill_hash"],
            mb["skill"]["skill_hash"],
        ),
        ("대상 revision", ma["skill"]["revision"], mb["skill"]["revision"]),
        (
            "실행 모델 / judge 모델",
            f"{ma['options'].get('model')} / {ma['options'].get('judge_model')}",
            f"{mb['options'].get('model')} / {mb['options'].get('judge_model')}",
        ),
        (
            "허용 도구",
            ",".join(ma["options"].get("allow_tools", [])),
            ",".join(mb["options"].get("allow_tools", [])),
        ),
        (
            "judge 라운드 / 동시성",
            f"{ma['options']['judge_rounds']} / {ma['options']['concurrency']}",
            f"{mb['options']['judge_rounds']} / {mb['options']['concurrency']}",
        ),
        (
            "Claude CLI",
            ma["dependencies"].get("claude_version"),
            mb["dependencies"].get("claude_version"),
        ),
    ):
        same = va == vb
        env_rows.append(
            f'<tr class="{"same" if same else "diff"}"><td>{esc(key)}</td><td><code>{esc(va)}</code></td><td><code>{esc(vb)}</code></td><td>{"동일" if same else "다름"}</td></tr>'
        )

    notes_block = (
        f'<section class="card notes"><h2>해석 (분석자 노트)</h2>{notes_html(Path(notes).read_text())}</section>'
        if notes
        else ""
    )

    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(skill)} 평가 비교</title><style>
:root{{color-scheme:light;--surface:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7873;--line:#e4e2dc;--before:#9a9891;--after:#2a78d6;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);background:var(--surface);line-height:1.55}}
body{{max-width:1180px;margin:auto;padding:28px 20px 60px}}h1{{font-size:1.7rem;margin:0 0 6px}}h2{{font-size:1.15rem;margin:0 0 12px}}h3{{font-size:1rem;margin:14px 0 6px}}h4{{margin:12px 0 4px;font-size:.95rem}}
.verdict{{font-size:1.05rem;color:var(--ink2);margin:0 0 20px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:16px 0}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.tile{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}.tile .label{{font-size:.8rem;color:var(--ink2)}}.tile .value{{font-size:1.25rem;font-weight:600;margin:4px 0}}.tile .before{{color:var(--ink2)}}.tile .arrow{{margin:0 6px;color:var(--muted)}}.tile .after{{color:var(--ink)}}
.delta{{font-size:.85rem;font-weight:600}}.delta.good{{color:#006300}}.delta.bad{{color:var(--critical)}}.delta.flat{{color:var(--muted);font-weight:400}}
ul.insights{{padding-left:20px;margin:0}}ul.insights li{{margin:6px 0}}.notes ul{{padding-left:20px}}.notes li{{margin:8px 0}}
.dim{{margin:8px 0 12px}}.dim-label{{font-weight:600;font-size:.92rem}}.bar-row{{display:flex;align-items:center;gap:8px;margin:3px 0}}.bar{{display:inline-block;height:10px;border-radius:0 4px 4px 0;min-width:2px}}.bar.before{{background:var(--before)}}.bar.after{{background:var(--after)}}.bar-val{{font-size:.85rem;color:var(--ink2);white-space:nowrap}}
.legend{{font-size:.85rem;color:var(--ink2);margin-bottom:6px}}.legend i{{display:inline-block;width:12px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}}
table{{width:100%;border-collapse:collapse;background:var(--card)}}th,td{{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.92rem}}th{{color:var(--ink2);font-weight:600;font-size:.82rem}}.table{{overflow:auto}}
.v-PASS{{color:#006300;font-weight:600}}.v-FAIL{{color:var(--critical);font-weight:600}}.v-ERROR{{color:#8a4b00;font-weight:600}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.8rem;font-weight:600;border:1px solid transparent}}.badge.good{{color:#006300;background:#e8f6e8;border-color:#b9e2b9}}.badge.critical{{color:var(--critical);background:#fbe9e9;border-color:#f1bcbc}}.badge.serious{{color:#8a3a12;background:#fdece3;border-color:#f5c8b0}}.badge.warning{{color:#6d4a00;background:#fff4d6;border-color:#f3dc9a}}.badge.neutral{{color:var(--ink2);background:#f1f0ec;border-color:var(--line)}}
tr.improved{{background:#f2faf2}}tr.same-fail,tr.regressed{{background:#fdf3f0}}tr.diff{{background:#fdecea}}
details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:10px 0}}summary{{cursor:pointer;font-weight:600}}dt{{font-weight:600;margin-top:10px}}dd{{margin:4px 0 8px 14px}}.q{{color:var(--ink2)}}
.muted{{color:var(--muted)}}.small{{font-size:.85rem}}code{{font-size:.8rem;overflow-wrap:anywhere}}a{{color:#0563a4}}.terms dt{{margin-top:8px}}
@media(max-width:600px){{body{{padding:16px 14px}}h1{{font-size:1.35rem}}}}
</style></head><body>
<header><h1>{esc(skill)} 평가 비교: {esc(label_a)} → {esc(label_b)}</h1><p class="verdict">{verdict}</p>
<p class="muted small">{esc(label_a)} = <code>{esc(sa["run_id"])}</code> · {esc(label_b)} = <code>{esc(sb["run_id"])}</code> · 같은 기준·harness·모델·옵션, 대상 스킬만 변경</p></header>

<section class="card"><h2>핵심 인사이트 (자동 계산)</h2><ul class="insights">{"".join(insights)}</ul></section>
{notes_block}
<section class="tiles">{"".join(tiles)}</section>

<section class="card"><h2>차원별 평균 점수 (1~5, 채점된 case 평균)</h2><div class="legend">범례: <i style="background:var(--before)"></i>{esc(label_a)} <i style="background:var(--after)"></i>{esc(label_b)}</div>{"".join(bars)}
<p class="muted small">composite = 호출 0.10 + 효율 0.10 + 모범 사례 0.15 + 실용성 0.15 + 작업 완수 0.50. 실용성은 작은 fixture라 상한이 낮다(측정된 사업 효과가 아님).</p></section>

<section class="card table"><h2>case별 결과</h2><table><thead><tr><th>ID</th><th>무엇을 검사했나</th><th>분류</th><th>{esc(label_a)}</th><th>{esc(label_b)}</th><th>변화</th><th>worker · 시간</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>

<section><h2>case별 근거 (실패한 case는 펼쳐져 있음)</h2>{"".join(details)}</section>

<section class="card terms"><h2>용어</h2><dl>
<dt>PASS / FAIL / ERROR</dt><dd>PASS는 composite 3.0 이상이면서 모든 필수(critical) 검사와 결정적 검사를 통과한 경우. FAIL은 그 중 하나라도 어긋난 경우. ERROR는 스킬이 아니라 평가 인프라 문제로 점수를 낼 수 없는 경우.</dd>
<dt>필수(critical) 검사</dt><dd>judge 3명이 각각 1~5점으로 매기고 중앙값을 쓴다. 중앙값이 3점 미만이면 composite와 무관하게 FAIL. 각 점수의 의미는 case마다 한국어 앵커 문장으로 정해져 있다.</dd>
<dt>결정적 검사</dt><dd>모델 판단 없이 파일로 확인: 보호 파일 sha256, 필수 산출물 존재, 필수 문구, 스킬 호출 여부.</dd>
<dt>worker</dt><dd>조율자가 Agent 도구로 띄운 하위 에이전트 수. 부모/worker 구분은 trace의 parent_tool_use_id로 판정하며 응답 본문의 자기보고는 근거로 쓰지 않는다.</dd>
</dl></section>

<details><summary>환경 대조 (paired run 조건)</summary><table><thead><tr><th>항목</th><th>{esc(label_a)}</th><th>{esc(label_b)}</th><th>동일?</th></tr></thead><tbody>{"".join(env_rows)}</tbody></table></details>

<footer class="muted small"><p>원본 보고서: <a href="{rel(out_dir, ra, "REPORT.html")}">{esc(label_a)} REPORT.html</a> · <a href="{rel(out_dir, rb, "REPORT.html")}">{esc(label_b)} REPORT.html</a> · <a href="{rel(out_dir, ra, "manifest.json")}">manifest {esc(label_a)}</a> · <a href="{rel(out_dir, rb, "manifest.json")}">manifest {esc(label_b)}</a>. 비용은 CLI 목록가 추정이며 청구서가 아니다.</p></footer>
</body></html>"""
    out.write_text(page)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label-a", default="before")
    ap.add_argument("--label-b", default="after")
    ap.add_argument("--notes", help="optional Markdown file rendered as analyst notes")
    args = ap.parse_args()
    print(
        build(args.before, args.after, args.out, args.label_a, args.label_b, args.notes)
    )
