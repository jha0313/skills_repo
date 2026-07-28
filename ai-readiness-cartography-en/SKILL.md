---
name: ai-readiness-cartography-en
description: Audits any repository against the v2 AI-Ready rubric (100 pts · 7 categories — Navigation, Context Quality, Tribal Knowledge, Dependency Mapping, Verification Gates, Freshness, Agent Outcomes) and produces a professional single-file HTML dashboard plus an ROI-ranked action list. The skill bundles a Python scorer (`scripts/score.py`) that auto-detects coverage, hallucinated paths, drift, and god files. Trigger whenever the user asks for an "AI-readiness map", "AI-ready visualization", "repo cartography", "codebase audit visualization", "ai-readiness-cartography", or anything that sounds like "score how agent-friendly this codebase is and visualize it", "check how AI-ready our repo is", "map the repo against the rubric", or "audit our codebase for agent readiness". Also trigger when the user points at a repo and asks whether it is ready for coding agents / LLM workflows — even without the exact keyword. The output is always a clean technical-dashboard HTML (Inter + JetBrains Mono, light surface, blue/green/amber/red accents), never a fantasy map.
---

# AI-Readiness Cartography

This skill audits any repository against the **AI-Ready Codebase v2 rubric** (100 pts · 7 categories A–G). The deliverables are a single professional technical-dashboard HTML, an auto-scored JSON, and an action list sorted by ROI. The name says "cartography," but the tone is a decision-making instrument panel — never fantasy parchment, compass roses, or similar ornaments.

## When to use

- "Give me an AI-readiness map / visualization / score"
- "Show me how agent-friendly this repo is"
- "codebase audit", "repo cartography"
- Indirect phrasings like "can Claude Code handle this repo well?"
- Trigger even without keywords if the user wants an LLM-workflow fitness assessment

## What to produce

**Produce all three deliverables at once.**

1. **JSON scorecard** (raw data, consumable by other tools)
2. **Single HTML dashboard** (for humans to read and decide)
3. **ROI-ranked action list** (prioritized next steps)

Default save-location priority:
- If the repo has `docs/` → `docs/ai-readiness-map.html`, `docs/ai-readiness-score.json`
- If it has `.claude/` → `.claude/ai-readiness-{map.html,score.json}`
- Otherwise the repo root
- If the user specifies an explicit path, that path wins

## Workflow

### 1. Auto-score with the Python script

```bash
python3 ~/.claude/skills/ai-readiness-cartography-en/scripts/score.py <repo-path> \
  --json <output-path>/ai-readiness-score.json
```

The script is stdlib only (no deps, Python 3.10+). Output:
- A structured scorecard at the `--json` path (categories A–G, evidence, sub_scores, findings, ROI actions, large files)
- A human-readable markdown summary on stdout

What scoring catches automatically:
- **A** Navigation coverage of core modules (ratio that hold CLAUDE.md / AGENTS.md)
- **B1, B5** conciseness · cross-references
- **C Q1–Q4** Five-Question framework heuristic + Q5 MEMORY/ADR presence
- **D** ARCHITECTURE.md / mermaid / workspace file detection
- **E1** **hallucinated path verification** (verify every path candidate in the context against actual existence) — this item matters most
- **E3** build/test infra presence
- **F** context drift (mtime comparison) + CI / hook validation
- **G** evals/ benchmarks/ directories + telemetry hints

What it cannot catch (Manual):
- The depth of B2–B4 quick commands / key files / non-obvious patterns
- The tribal-knowledge depth in C
- The quality of the E2 critic review
- The quality of E4 prompt tests

After the LLM receives the JSON, it can supplement the manual items or reflect them in the charts as-is.

### 2. Fill the HTML dashboard from the JSON

Copy `assets/template.html` and slot in the JSON values. **Never write it from scratch** — the design would drift every time.

Blocks to replace:

**(a) Header**
- `<title>` · the `{{REPO_NAME}}` in h1
- The date (today) · git branch · `meta.modules_total` · `meta.context_files_total` in `header-meta`

**(b) Score hero**
- `score-hero .num` ← `total`
- `grade-badge` text ← grade (`AI-Native` / `AI-Ready` / `AI-Assisted` / `AI-Fragile` / `AI-Hostile`)
- `grade-badge` background/color ← `grade_color` (green / amber / red)
- Grade thresholds:
  - 90-100 AI-Native (green)
  - 75-89  AI-Ready (green)
  - 60-74  AI-Assisted (amber)
  - 40-59  AI-Fragile (amber)
  - < 40   AI-Hostile (red)
- `.desc` mentions the two weakest categories in one line
- Three mini stats: modules · context_files · large_files_300plus (or emphasize ref_broken)

**(c) Seven-category bar chart**
Replace the 10-rule chart with the 7 categories. Each row:
- A 15 / B 20 / C 20 / D 15 / E 15 / F 10 / G 5
- bar width = `score / max * 100%`
- color: score/max ≥ 0.75 → bar-good (green) · 0.5–0.74 → bar-warn (amber) · < 0.5 → bar-bad (red)
- `.sub` carries 1–2 short evidence snippets (e.g. "coverage 75% · 1 module missing")
- B and E have sub_scores, so expand a small breakdown under their rows to show the 5/4 sub-item scores too

**(d) Structural Map (SVG)**
Reconfigure the columns to match the target repo's structure. Inside each card, show the top `large_files` entries as hot/warm bars. Modules that hold CLAUDE.md / AGENTS.md get an accent border + lit dot. Modules with `ref_broken` get a red dot.

**(e) Wins / Top ROI Actions panel**
- Left "Wins": the highest-scoring categories from the evidence, 5 key strengths
- Right "Top ROI Actions": the top 5–7 from the JSON `actions`. Each row shows:
  - Category tag (A–G)
  - Effort (S / M / L · hours)
  - Impact (one line)
  - Priority score (optional)

**(f) Footer**
`{{REPO_NAME}} · AI-Readiness v2 · scored {{YYYY-MM-DD}}`

### 3. Open in the browser

```bash
open <output-path>/ai-readiness-map.html   # macOS
xdg-open <path>                            # Linux
```

If the user says "don't open it," just report the path.

### 4. Summary report

Finally, give these four things in one paragraph:
1. **Total / grade** (`32/100 · AI-Hostile`)
2. **The 1–2 weakest categories** + a one-line diagnosis
3. **Top 3 ROI actions** (Effort + Impact, briefly)
4. The generated **file paths**

## Style rules (non-negotiable)

These are the skill's identity. Deviate and it stops being this skill.

- **Fonts**: Inter (body), JetBrains Mono (numbers/code). No other fonts.
- **Colors**: lock to the template's CSS-variable palette.
- **Background**: `#fafafa` light. Do not build a dark mode.
- **No ornaments**: compass roses, parchment, cursive scripts, emoji, stamps — none.
- **No chart libraries**: every visualization is inline SVG + CSS.

## Common pitfalls

- **Forgetting the rubric is v2 and scoring with the 10-rule version** — a leftover from a previous version. The current rubric is **A–G, 7 categories, 100 pts**.
- **Ignoring the script output and scoring by hand** — what the script catches, it catches more accurately. Run the script first, then supplement on top.
- **Treating E1 hallucinated paths lightly** — the Meta standard is "0 hallucinated paths." Even one means an immediate fix action.
- **Ignoring the template and writing from scratch** — the design drifts every time. Copy → edit.
- **Regressing to fantasy** — even though the name is cartography, do not lean hard on map metaphors.
- **Qualitative-adjective-only ROI** — vague impacts like "efficiency ↑" are banned. Use concrete units like "~3 min per task × ~5/day."

## ROI framing

Conventions for each action's effort/impact:

- **Effort**: S (<1h) / M (1–4h) / L (4h+)
- **Impact**: quantitative units first — "N min per task × M tasks/week", "X% token reduction", "catches Y regressions"
- **Priority**: auto-sorted by `impact_score / effort_hours`

See the ROI table at the end of `references/scoring-rubric.md` for representative actions.

## Files

- `assets/template.html` — the source dashboard to copy and fill
- `references/scoring-rubric.md` — the 7-category scoring criteria v2
- `scripts/score.py` — auto-scoring + ROI action generation (Python 3.10+, stdlib only)
