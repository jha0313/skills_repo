"""Paired before/after dashboard for two canonical skill-evaluator runs.

Reporting only: reads summary.json / manifest.json / criteria.yaml / cases/*/metadata.json
of two finished runs and writes one self-contained HTML next to them. It never
re-grades or edits a run. Optional analyst notes (Markdown) are rendered in their own
blocks so computed facts and human interpretation stay separate.

Page order is a plain-language story first, details last:
result (pass counts) → one dot per case → analyst findings → next steps → everything
else (tiles, dimension bars, table, per-case evidence, terms, environment) collapsed.

Notes format (all sections optional; other `## ` sections render in the collapsed area):

    ## 결론
    one or two sentences
    ## 발견
    ### finding title
    - 문제: ...
    - 증거: ...
    - 조치: ...
    - 결과: ...
    ## 다음 할 일
    - ...
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
VERDICT_KO = {"PASS": "통과", "FAIL": "실패", "ERROR": "오류"}
STORY_SECTIONS = ("결론", "발견", "다음 할 일")


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
        return "improved", "개선", "good"
    if a == "PASS" and b != "PASS":
        return "regressed", "악화", "critical"
    if b == "PASS":
        return "same-pass", "통과 유지", "neutral"
    if b == "ERROR":
        return "error", "평가 오류", "warning"
    return "same-fail", "여전히 실패", "serious"


def failing_reasons(run, out_dir, result, spec):
    """Korean rubric anchors at the voted score for critical misses, plus deterministic failures."""
    items = []
    if result.get("status") == "error":
        items.append(("평가 인프라 오류", esc(result.get("error"))))
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
                f"<li>심판 {i}: {j['score']}점 — {esc(j.get('reason', ''))}</li>"
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
                    f"필수 조건 q{sem['index']} 미달 (심판 중앙값 {sem['score']}점, 3점 미만이면 실패)",
                    f'<p class="q">{esc(q["question"].split(" 이 항목은")[0])}</p>'
                    f"<p><b>판정 기준 ({sem['score']}점):</b> {esc(anchor)}</p>"
                    f"<details><summary>심판 3명의 이유 (영문 원문)</summary><ul>{rounds}</ul></details>",
                )
            )
    if not items and result.get("verdict") != "PASS":
        items.append(("가중 합 점수 미달", f"{fmt(result.get('score'))} < 3.0"))
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


def inline(text):
    """Minimal inline markdown: **bold** only; everything else escaped."""
    parts = text.split("**")
    return "".join(
        (f"<b>{esc(p)}</b>" if i % 2 else esc(p)) for i, p in enumerate(parts)
    )


def parse_notes(text):
    """Split analyst Markdown into ordered (heading, nonblank lines) by `## `."""
    sections, heading, lines = [], None, []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            if heading is not None or lines:
                sections.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif line:
            lines.append(line)
    if heading is not None or lines:
        sections.append((heading, lines))
    return sections


def render_paragraphs(lines):
    return "".join(f"<p>{inline(line)}</p>" for line in lines)


def render_bullets(lines):
    items = [
        inline(line[2:]) if line.startswith(("- ", "* ")) else inline(line)
        for line in lines
    ]
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def render_findings(lines):
    """`### title` starts a card; `- 라벨: 내용` becomes a labelled row inside it."""
    cards, cur = [], None
    for line in lines:
        if line.startswith("### "):
            cur = {"title": line[4:].strip(), "rows": []}
            cards.append(cur)
        elif cur is None:
            continue
        elif line.startswith(("- ", "* ")):
            body = line[2:]
            label, sep, rest = body.partition(":")
            if sep and rest.strip() and len(label.strip()) <= 8:
                cur["rows"].append((label.strip(), rest.strip()))
            else:
                cur["rows"].append(("", body))
        else:
            cur["rows"].append(("", line))
    out = []
    for i, c in enumerate(cards, 1):
        rows = "".join(
            f'<div class="row"><span class="k">{esc(k)}</span><span class="v">{inline(v)}</span></div>'
            for k, v in c["rows"]
        )
        out.append(
            f'<article class="finding"><div class="fn">{i}</div><h3>{inline(c["title"])}</h3>{rows}</article>'
        )
    return "".join(out)


def notes_html(text):
    """Generic minimal markdown for sections outside the story blocks."""
    out = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("### "):
            out.append(f"<h4>{inline(line[4:])}</h4>")
        elif line.startswith("## "):
            out.append(f"<h3>{inline(line[3:])}</h3>")
        elif line.startswith(("- ", "* ")):
            out.append(f"<li>{inline(line[2:])}</li>")
        else:
            out.append(f"<p>{inline(line)}</p>")
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

    # ---- analyst notes (human interpretation, kept separate from computed facts) ----
    sections = parse_notes(Path(notes).read_text()) if notes else []
    by_head = {h: lines for h, lines in sections}
    conclusion = render_paragraphs(by_head.get("결론", []))
    findings = render_findings(by_head.get("발견", []))
    next_steps = render_bullets(by_head.get("다음 할 일", []))
    other_notes = "".join(
        notes_html(("## " + h + "\n" if h else "") + "\n".join(lines))
        for h, lines in sections
        if h not in STORY_SECTIONS
    )

    # ---- computed facts -------------------------------------------------------
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

    # ---- hero: the result in one glance ---------------------------------------
    changed_bits = []
    if improved:
        changed_bits.append(f"{len(improved)}개가 실패에서 통과로")
    if regressed:
        changed_bits.append(f"{len(regressed)}개가 통과에서 실패로")
    if still_failing:
        changed_bits.append(f"{len(still_failing)}개는 여전히 실패")
    hero_sub = (
        ", ".join(changed_bits) + "." if changed_bits else "달라진 시험이 없습니다."
    )

    # ---- one dot per case --------------------------------------------------------
    order = {"improved": 0, "regressed": 1, "same-fail": 2, "error": 2, "same-pass": 3}
    dots = []
    for cid in sorted(
        res_a, key=lambda c: (order[status_of(res_a[c], res_b.get(c, {}))[0]], c)
    ):
        a, b = res_a[cid], res_b.get(cid, {})
        kind, label, tone = status_of(a, b)
        va, vb = a.get("verdict"), b.get("verdict")
        dots.append(
            f'<a class="dot-card {kind}" href="#{cid}" title="{esc(spec[cid]["description"])}">'
            f'<div class="dot-id">{cid}</div><div class="dot-name">{esc(spec[cid]["name"])}</div>'
            f'<div class="dots"><span class="dot {esc(va)}" aria-label="{esc(label_a)} {VERDICT_KO.get(va, va)}"></span>'
            f'<span class="darrow">→</span><span class="dot {esc(vb)}" aria-label="{esc(label_b)} {VERDICT_KO.get(vb, vb)}"></span>'
            f'<span class="badge {tone}">{label}</span></div></a>'
        )

    # ---- auto summary (kept, but collapsed) ----------------------------------------
    insights = []
    insights.append(
        f"<li><b>통과 시험 {sa['passed']} → {sb['passed']} ({sa['total']}개 중).</b> "
        + (
            "개선: " + ", ".join(f"{c} {esc(n)}" for c, n in improved) + ". "
            if improved
            else "개선된 시험 없음. "
        )
        + (
            "악화: " + ", ".join(f"{c} {esc(n)}" for c, n in regressed) + ". "
            if regressed
            else ""
        )
        + (
            "여전히 실패: " + ", ".join(f"{c} {esc(n)}" for c, n in still_failing) + "."
            if still_failing
            else "실패 시험 없음."
        )
        + "</li>"
    )
    for cid, name in still_failing:
        reasons = failing_reasons(rb, out_dir, res_b[cid], spec[cid])
        heads = "; ".join(esc(h) for h, _ in reasons)
        insights.append(
            f"<li><b>{cid} {esc(name)}은(는) 고친 뒤에도 실패.</b> 이유: {heads}. "
            f'<a href="#{cid}">근거 보기</a></li>'
        )
    if exec_cases:
        insights.append(
            f"<li><b>실행형 시험 {len(exec_cases)}개의 worker 수 합계 {agents_a} → {agents_b}, "
            f"실행 시간 합계 {dur_a:.0f}초 → {dur_b:.0f}초.</b> 각 시험은 한 번씩만 실행했으므로 "
            f"방향만 참고하고 크기는 변동 범위 안일 수 있다.</li>"
        )
    if dim_moves:
        insights.append(
            "<li><b>0.1 이상 움직인 관점:</b> "
            + ", ".join(f"{DIM_KO[d]} {a:.2f} → {b:.2f}" for d, a, b in dim_moves)
            + ". 나머지는 사실상 동일.</li>"
        )
    else:
        insights.append(
            "<li><b>다섯 관점 평균은 모두 0.1 미만으로 움직였다.</b> 점수 차이보다 통과/실패의 이유를 보라.</li>"
        )
    insights.append(
        f"<li><b>비용·시간:</b> 실행+채점 비용 {fmt(sa.get('execution_and_judge_cost_usd'))} → "
        f"{fmt(sb.get('execution_and_judge_cost_usd'))} USD(CLI 추정), 전체 소요 "
        f"{(sa.get('wall_clock_seconds') or 0) / 60:.0f}분 → {(sb.get('wall_clock_seconds') or 0) / 60:.0f}분. "
        f"채점 재시도 {retries_a}회 → {retries_b}회(재시도된 라운드는 새 세션으로 다시 채점됨).</li>"
    )
    insights.append(
        "<li><b>신뢰도:</b> 같은 시험·채점 도구·모델·옵션에서 스킬만 바꾼 관찰 비교다. "
        "심판 3명의 중앙값은 변동을 줄이지만 편향을 없애지 않으며, 한 번의 전후 비교로 인과를 주장하지 않는다.</li>"
    )

    # ---- stat tiles ----------------------------------------------------------
    tiles = []
    for label, a, b, digits, up_good, unit in (
        ("통과한 시험", sa["passed"], sb["passed"], 0, True, ""),
        ("통과율", sa["pass_rate"], sb["pass_rate"], 2, True, ""),
        ("평균 점수 (1~5)", sa.get("score"), sb.get("score"), 2, True, ""),
        (
            "실행 비용 (USD 추정)",
            sa.get("execution_cost_usd"),
            sb.get("execution_cost_usd"),
            2,
            False,
            "",
        ),
        (
            "채점 비용 (USD 추정)",
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
            f'<td class="v-{a["verdict"]}">{VERDICT_KO.get(a["verdict"], a["verdict"])} {fmt(a.get("score"))}</td>'
            f'<td class="v-{b.get("verdict")}">{VERDICT_KO.get(b.get("verdict"), b.get("verdict"))} {fmt(b.get("score"))}</td>'
            f'<td><span class="badge {tone}">{label}</span></td><td class="small">{effort}</td></tr>'
        )
        blocks = []
        for tag, run, r in ((label_a, ra, a), (label_b, rb, b)):
            if r and r.get("verdict") != "PASS":
                items = failing_reasons(run, out_dir, r, spec[cid])
                blocks.append(
                    f"<h4>{esc(tag)}: {VERDICT_KO.get(r.get('verdict'), r.get('verdict'))} (점수 {fmt(r.get('score'))})</h4><dl>"
                    + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items)
                    + "</dl>"
                )
        head = f'<summary>{cid} — {esc(spec[cid]["name"])} <span class="badge {tone}">{label}</span></summary><p class="muted small">프롬프트: {esc(spec[cid]["prompt"])}</p>'
        links = f'<p class="small">근거 {esc(label_a)}: {case_links(ra, out_dir, cid)}<br>근거 {esc(label_b)}: {case_links(rb, out_dir, cid)}</p>'
        details.append(
            f'<details id="{cid}"{" open" if blocks else ""}>{head}{"".join(blocks)}{links}</details>'
        )

    # ---- environment fingerprint ------------------------------------------------
    env_rows = []
    for key, va, vb in (
        ("시험 문제 hash", ma["criteria_hash"], mb["criteria_hash"]),
        ("채점 도구 hash", ma["evaluator_hash"], mb["evaluator_hash"]),
        (
            "대상 스킬 hash (달라야 정상)",
            ma["skill"]["skill_hash"],
            mb["skill"]["skill_hash"],
        ),
        ("대상 revision", ma["skill"]["revision"], mb["skill"]["revision"]),
        (
            "실행 모델 / 심판 모델",
            f"{ma['options'].get('model')} / {ma['options'].get('judge_model')}",
            f"{mb['options'].get('model')} / {mb['options'].get('judge_model')}",
        ),
        (
            "허용 도구",
            ",".join(ma["options"].get("allow_tools", [])),
            ",".join(mb["options"].get("allow_tools", [])),
        ),
        (
            "심판 라운드 / 동시성",
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

    story = ""
    if findings:
        story += f'<section><h2>무엇을 발견했나</h2><p class="muted">분석자가 실행 기록을 읽고 정리한 해석입니다. 각 카드의 "증거"에서 근거 시험을 확인할 수 있습니다.</p><div class="findings">{findings}</div></section>'
    if by_head.get("다음 할 일"):
        story += f'<section class="card next"><h2>다음 할 일</h2>{next_steps}</section>'

    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(skill)} 고치기 전·후 비교</title><style>
:root{{color-scheme:light;--surface:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7873;--line:#e4e2dc;--before:#9a9891;--after:#2a78d6;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);background:var(--surface);line-height:1.6}}
body{{max-width:1080px;margin:auto;padding:36px 20px 60px}}h1{{font-size:1.9rem;margin:0 0 6px;letter-spacing:-.02em}}h2{{font-size:1.3rem;margin:0 0 12px}}h3{{font-size:1.05rem;margin:0 0 10px}}h4{{margin:12px 0 4px;font-size:.95rem}}section{{margin:36px 0}}
.sub{{color:var(--ink2);margin:0 0 8px;font-size:1rem}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin:14px 0}}
.hero{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 28px;margin:20px 0 8px}}.hero-num{{font-size:2.4rem;font-weight:800;letter-spacing:-.03em;line-height:1.1}}.hero-num .before{{color:var(--before)}}.hero-num .after{{color:var(--after)}}.hero-num .of{{font-size:1.1rem;font-weight:600;color:var(--ink2);margin-left:8px}}.hero-sub{{font-size:1.05rem;color:var(--ink2);margin:8px 0 0}}.hero .conclusion{{margin-top:14px;padding-top:14px;border-top:1px solid var(--line)}}.hero .conclusion p{{margin:0 0 6px;font-size:1.05rem}}
.legend{{font-size:.88rem;color:var(--ink2);margin:0 0 10px}}.legend .dot{{margin:0 4px 0 12px;vertical-align:middle;width:12px;height:12px}}
.dot-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}}.dot-card{{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 14px 12px;text-decoration:none;color:inherit;transition:box-shadow .15s}}.dot-card:hover{{box-shadow:0 4px 14px rgba(0,0,0,.08)}}.dot-card.improved{{border-color:#b9e2b9;background:#f4fbf4}}.dot-card.same-fail,.dot-card.regressed,.dot-card.error{{border-color:#f1bcbc;background:#fdf5f3}}
.dot-id{{font-size:.75rem;font-weight:700;color:var(--muted);letter-spacing:.04em}}.dot-name{{font-size:.92rem;font-weight:600;line-height:1.4;min-height:2.8em;margin:2px 0 8px}}.dots{{display:flex;align-items:center;gap:6px}}.dot{{display:inline-block;width:16px;height:16px;border-radius:50%;background:#ccc;flex:none}}.dot.PASS{{background:var(--good)}}.dot.FAIL{{background:var(--critical)}}.dot.ERROR{{background:var(--warning)}}.darrow{{color:var(--muted);font-size:.9rem}}.dots .badge{{margin-left:auto}}
.findings{{display:grid;gap:12px}}.finding{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px 14px 20px;position:relative}}.finding .fn{{position:absolute;left:-1px;top:-1px;background:var(--ink);color:#fff;font-weight:700;font-size:.8rem;width:30px;height:30px;border-radius:14px 0 12px 0;display:flex;align-items:center;justify-content:center}}.finding h3{{padding-left:26px;font-size:1.08rem}}.finding .row{{display:grid;grid-template-columns:52px 1fr;gap:10px;padding:6px 0;border-top:1px solid var(--line);font-size:.95rem}}.finding .row .k{{font-weight:700;color:var(--ink2)}}.finding .row .v{{color:var(--ink)}}
.next ul{{margin:0;padding-left:20px}}.next li{{margin:6px 0}}
details.deep{{background:transparent;border:0;padding:0;margin:28px 0 0}}details.deep>summary{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;font-size:1.05rem}}details.deep>summary::before{{content:"▸ ";color:var(--after)}}details.deep[open]>summary::before{{content:"▾ "}}details.deep>.deep-body{{padding-top:8px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.tile{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}.tile .label{{font-size:.8rem;color:var(--ink2)}}.tile .value{{font-size:1.25rem;font-weight:600;margin:4px 0}}.tile .before{{color:var(--ink2)}}.tile .arrow{{margin:0 6px;color:var(--muted)}}.tile .after{{color:var(--ink)}}
.delta{{font-size:.85rem;font-weight:600}}.delta.good{{color:#006300}}.delta.bad{{color:var(--critical)}}.delta.flat{{color:var(--muted);font-weight:400}}
ul.insights{{padding-left:20px;margin:0}}ul.insights li{{margin:6px 0}}.notes ul{{padding-left:20px}}.notes li{{margin:8px 0}}
.dim{{margin:8px 0 12px}}.dim-label{{font-weight:600;font-size:.92rem}}.bar-row{{display:flex;align-items:center;gap:8px;margin:3px 0}}.bar{{display:inline-block;height:10px;border-radius:0 4px 4px 0;min-width:2px}}.bar.before{{background:var(--before)}}.bar.after{{background:var(--after)}}.bar-val{{font-size:.85rem;color:var(--ink2);white-space:nowrap}}
.legend i{{display:inline-block;width:12px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}}
table{{width:100%;border-collapse:collapse;background:var(--card)}}th,td{{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.92rem}}th{{color:var(--ink2);font-weight:600;font-size:.82rem}}.table{{overflow:auto}}
.v-PASS{{color:#006300;font-weight:600}}.v-FAIL{{color:var(--critical);font-weight:600}}.v-ERROR{{color:#8a4b00;font-weight:600}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid transparent;white-space:nowrap}}.badge.good{{color:#006300;background:#e8f6e8;border-color:#b9e2b9}}.badge.critical{{color:var(--critical);background:#fbe9e9;border-color:#f1bcbc}}.badge.serious{{color:#8a3a12;background:#fdece3;border-color:#f5c8b0}}.badge.warning{{color:#6d4a00;background:#fff4d6;border-color:#f3dc9a}}.badge.neutral{{color:var(--ink2);background:#f1f0ec;border-color:var(--line)}}
tr.improved{{background:#f2faf2}}tr.same-fail,tr.regressed{{background:#fdf3f0}}tr.diff{{background:#fdecea}}
details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:10px 0}}summary{{cursor:pointer;font-weight:600}}dt{{font-weight:600;margin-top:10px}}dd{{margin:4px 0 8px 14px}}.q{{color:var(--ink2)}}
.muted{{color:var(--muted)}}.small{{font-size:.85rem}}code{{font-size:.8rem;overflow-wrap:anywhere}}a{{color:#0563a4}}.terms dt{{margin-top:8px}}
@media(max-width:600px){{body{{padding:20px 14px}}h1{{font-size:1.45rem}}.hero-num{{font-size:1.9rem}}.finding .row{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>{esc(skill)}: 고치기 전 → 고친 후</h1><p class="sub">같은 시험 {sa["total"]}개를 같은 조건으로 두 번 치렀습니다. 달라진 것은 스킬 문구뿐입니다. {esc(label_a)} = 전, {esc(label_b)} = 후.</p></header>

<div class="hero">
  <div class="hero-num"><span class="before">{sa["passed"]}</span> → <span class="after">{sb["passed"]}</span><span class="of">/ {sa["total"]} 통과</span></div>
  <p class="hero-sub">{hero_sub}</p>
  {f'<div class="conclusion">{conclusion}</div>' if conclusion else ""}
</div>

<section><h2>시험 {sa["total"]}개, 한눈에</h2>
<p class="legend">왼쪽 점 = {esc(label_a)}, 오른쪽 점 = {esc(label_b)}. <span class="dot PASS"></span>통과 <span class="dot FAIL"></span>실패 <span class="dot ERROR"></span>평가 오류. 카드를 누르면 근거로 이동합니다.</p>
<div class="dot-grid">{"".join(dots)}</div></section>

{story}

<details class="deep"><summary>자세히 보기 — 숫자, 관점별 점수, 시험별 표와 근거, 용어, 환경</summary><div class="deep-body">

<section class="tiles">{"".join(tiles)}</section>

<section class="card"><h2>자동 계산 요약</h2><ul class="insights">{"".join(insights)}</ul></section>
{f'<section class="card notes">{other_notes}</section>' if other_notes else ""}

<section class="card"><h2>다섯 관점 평균 점수 (1~5)</h2><div class="legend">범례: <i style="background:var(--before)"></i>{esc(label_a)} <i style="background:var(--after)"></i>{esc(label_b)}</div>{"".join(bars)}
<p class="muted small">가중 합 = 호출 판단 0.10 + 효율 0.10 + 모범 사례 0.15 + 실용성 0.15 + 작업 완수 0.50. 실용성은 작은 연습 파일이라 상한이 낮다(측정된 사업 효과가 아님).</p></section>

<section class="card table"><h2>시험별 결과</h2><table><thead><tr><th>ID</th><th>무엇을 검사했나</th><th>분류</th><th>{esc(label_a)}</th><th>{esc(label_b)}</th><th>변화</th><th>worker · 시간</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>

<section><h2>시험별 근거 (실패한 시험은 펼쳐져 있음)</h2>{"".join(details)}</section>

<section class="card terms"><h2>용어</h2><dl>
<dt>통과 / 실패 / 평가 오류</dt><dd>통과는 가중 합 점수 3.0 이상이면서 모든 필수 조건과 결정적 검사를 지킨 경우. 실패는 그 중 하나라도 어긋난 경우. 평가 오류는 스킬이 아니라 채점 도구 문제로 점수를 낼 수 없는 경우.</dd>
<dt>필수 조건</dt><dd>심판 3명이 각각 1~5점으로 매기고 중앙값을 쓴다. 중앙값이 3점 미만이면 가중 합과 무관하게 실패. 각 점수의 의미는 시험마다 한국어 기준 문장으로 정해져 있다.</dd>
<dt>결정적 검사</dt><dd>모델 판단 없이 파일로 확인: 보호 파일 sha256, 필수 산출물 존재, 필수 문구, 스킬 호출 여부.</dd>
<dt>worker</dt><dd>조율자가 Agent 도구로 띄운 하위 에이전트 수. 부모/worker 구분은 실행 기록의 parent_tool_use_id로 판정하며 응답 본문의 자기보고는 근거로 쓰지 않는다.</dd>
</dl></section>

<details><summary>환경 대조 (같은 조건이었는지)</summary><table><thead><tr><th>항목</th><th>{esc(label_a)}</th><th>{esc(label_b)}</th><th>동일?</th></tr></thead><tbody>{"".join(env_rows)}</tbody></table></details>

<footer class="muted small"><p>{esc(label_a)} = <code>{esc(sa["run_id"])}</code> ({ver_a}) · {esc(label_b)} = <code>{esc(sb["run_id"])}</code> ({ver_b}). 원본 보고서: <a href="{rel(out_dir, ra, "REPORT.html")}">{esc(label_a)}</a> · <a href="{rel(out_dir, rb, "REPORT.html")}">{esc(label_b)}</a> · <a href="{rel(out_dir, ra, "manifest.json")}">manifest {esc(label_a)}</a> · <a href="{rel(out_dir, rb, "manifest.json")}">manifest {esc(label_b)}</a>. 비용은 CLI 목록가 추정이며 청구서가 아니다.</p></footer>
</div></details>
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
