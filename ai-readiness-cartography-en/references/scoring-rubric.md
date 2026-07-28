# AI-Ready Codebase Rubric · v2 (100 pt · 7 categories)

This document is the single source of truth for both automatic and manual scoring. Items that `scripts/score.py` cannot catch automatically are supplemented by a human — the **Auto / Heuristic / Manual** tag at the end of each item tells you how much to trust it.

| Cat | Name | Points |
|-----|------|--------|
| A | AI Navigation & Coverage | 15 |
| B | Context Document Quality | 20 |
| C | Tribal Knowledge Externalization | 20 |
| D | Cross-Module Dependency & Data Flow Mapping | 15 |
| E | Verification & Quality Gates | 15 |
| F | Freshness & Self-Maintenance | 10 |
| G | Agent Performance Outcomes | 5 |

**Total = 100**

---

## A. AI Navigation & Coverage · /15

> Can the AI quickly find the whole codebase / modules / workflows?

| Score | Criteria |
|-------|----------|
| 0     | Have to guess at the repo with grep / search |
| 5     | Some modules have a README / context |
| 10    | Most core modules have their role · entry point · related files written down |
| 15    | Every core module / workflow has a navigation guide. "Where do I look?" is reachable within 1–2 hops |

**Measurement** *(Auto)*

```
Navigation Coverage = (core modules reachable via AI context) / (total core modules)
```

- "Core module" = code directories at the repo root + each child of `apps/*` / `packages/*` / `services/*`
- Score = `round(coverage × 15)`, then capped
- Evaluated by module / workflow coverage, not by file count

---

## B. Context Document Quality · /20

> Do the context files follow the "compass, not encyclopedia" principle?

| Sub | Item | Points | Full-Score Criteria |
|-----|------|--------|---------------------|
| B1 | Conciseness *(Auto)*       | 4 | Every CLAUDE.md is 25–35 lines or under ~1,000 tokens |
| B2 | Quick Commands *(Heuristic)* | 4 | Copy-paste-able commands + when to use them (`~~~bash` block + surrounding explanation) |
| B3 | Key Files *(Heuristic)*    | 4 | Provides the 3–5 key file paths actually needed for edits |
| B4 | Non-Obvious Patterns *(Heuristic)* | 4 | Failure-causing hidden rules + exceptions are stated (`Why:`, `Note:`, `Gotcha`, `Warning`) |
| B5 | See Also / Cross References *(Auto)* | 4 | Links related modules / context files / dependency maps (relative links) |

Each sub-item converts the module average or max into a 4-point scale. **The point is not lots of documents, but only task-relevant context.**

---

## C. Tribal Knowledge Externalization · /20

> Are hidden rules, failure patterns, and human-only knowledge structured?

### Five-Question Framework *(Heuristic + Manual)*

For each core module, 4 points each if you can answer these 5 questions, 20 total:

1. **What does this module configure / own?** — `## Purpose`, "configures", "owns" phrasing
2. **What are common modification patterns?** — `## Patterns`, "common changes", "## How to"
3. **What non-obvious patterns cause failures?** — `Why:`, `Note:`, `Gotcha`, `Don't`
4. **What are the cross-module dependencies?** — "depends on", "imports", `## Cross-module`
5. **What tribal knowledge is hidden in comments / history / human memory?** — presence of `MEMORY.md` / `ADR` / `docs/decisions`

### Score band

| Score | Criteria |
|-------|----------|
| 0     | Knowledge lives only in a senior engineer / Slack / past PRs |
| 5     | Some gotchas scattered across READMEs / comments |
| 10    | Some tacit knowledge of recurring work is documented |
| 15    | Compatibility rules / naming / generated-code rules / deprecated-but-required rules are written down |
| 20    | Most identified tribal knowledge is reflected in context files / checklists / playbooks + retrievable by AI via query |

Auto score = (avg of 5-question pass × 20). Real depth is verified by a human.

---

## D. Cross-Module Dependency & Data Flow Mapping · /15

> Can the AI trace the blast radius of a change?

| Score | Criteria |
|-------|----------|
| 0     | Change impact is traced manually by a human |
| 5     | Some architecture diagrams or dependency notes |
| 10    | Dependencies / ownership between major modules are documented |
| 15    | "What depends on X?" can be answered with a graph / index / map. Can trace repo / service / test / data-flow ripple |

**Auto checks:**
- Presence of `docs/architecture.md`, `ARCHITECTURE.md`, `docs/dependency-graph*`
- Presence of `mermaid` / `graphviz` diagram fences
- A `## Dependencies` / `Cross-module` section inside CLAUDE.md
- Whether a graph is derivable from a monorepo's `pnpm-workspace.yaml` / `turbo.json` / `nx.json`

**Why important.** Decisive in large codebases where one field change ripples to 6 subsystems. If this is weak, docking D is correct.

---

## E. Verification & Quality Gates · /15

> Is there a system to verify AI-generated context and code changes?

| Sub | Item | Points | Full-Score Criteria |
|-----|------|--------|---------------------|
| E1 | Reference Accuracy *(Auto)*        | 5 | 0 hallucinations among the file paths · APIs · commands mentioned in CLAUDE.md / context files |
| E2 | Independent Critic Review *(Manual)* | 4 | At least 2–3 rounds of independent review or a checklist (CODEOWNERS / review template / agent critic) |
| E3 | Task Validation *(Auto)*           | 4 | Provides build / test / lint / typecheck / e2e verification commands per change type + actually runnable |
| E4 | Prompt / Workflow Tests *(Heuristic)* | 2 | Representative AI task queries are actually tested (`evals/`, agent test) |

**E1 auto-scoring algorithm:**
1. Extract `[A-Za-z0-9_./-]+\.(py|ts|tsx|js|md|sql|json|yaml|yml|toml)` candidates from every context file
2. Verify each candidate's existence relative to the repo root
3. `valid / total` ratio → `round(ratio × 5)`

> In Meta's phrasing, "zero hallucinated paths" is the condition for a 5. This is the heart of AI-readiness — unverified context is **more dangerous** than no context.

---

## F. Freshness & Self-Maintenance · /10

> Is context auto-maintained so it doesn't go stale?

| Score | Criteria |
|-------|----------|
| 0     | Manually managed + staleness unknown |
| 3     | Has an owner + occasional updates |
| 6     | CI / scripts detect some broken paths / references |
| 10    | Periodic file-path validation, coverage-gap detection, critic review, stale-reference repair run automatically |

**Auto checks:**
- Compare each CLAUDE.md mtime vs the latest mtime of code files inside the same module — the drift ratio
- A context / docs validation step in `.github/workflows/*`
- A path-validation hook in pre-commit / husky
- The date of the most recent entry in `MEMORY.md` Session Notes

**Why emphasized.** Stale context legitimizes hallucination as augmented retrieval. It is **worse** than nothing.

---

## G. Agent Performance Outcomes · /5

> Is real AI task success rate / efficiency improvement measured?

| Score | Criteria |
|-------|----------|
| 0     | No AI performance measurement |
| 2     | Qualitatively "it helps" |
| 3     | Representative task success rate or human intervention rate is measured |
| 5     | tool calls, token usage, task completion time, correctness, prompt pass rate measured before / after |

**Tracked metrics (examples):**
- AI task pass rate
- Average tool calls per task
- Average tokens per task
- human clarification count
- failed PR / rework rate
- hallucinated file path count
- time-to-first-correct-change

**Auto checks:**
- Presence of `evals/`, `benchmarks/`, `agent-metrics/` directories
- Result files like `.skill-eval.json`, `agent-results.json`
- AI usage telemetry setup (Claude Code session log, OpenTelemetry)

---

## Final Grade

| Score | Level | Meaning | Badge color |
|-------|-------|---------|-------------|
| 90-100 | **AI-Native / Agentic-Ready** | Agent autonomously handles most recurring work + the context layer is self-maintaining | green |
| 75-89  | **AI-Ready** | AI navigates, edits, and verifies reliably for most work | green |
| 60-74  | **AI-Assisted** | AI is useful but complex / domain tasks need human context | amber |
| 40-59  | **AI-Fragile** | Simple tasks work, but high error risk from hidden rules / dependencies | amber |
| < 40   | **AI-Hostile** | Heavy reliance on tribal knowledge + AI works from guesses | red |

---

## ROI Heuristics for Recommendations

For each gap, present an action in this format:

```
Effort: S (<1h) / M (1-4h) / L (4h+)
Impact: time saved per AI task × estimated tasks/period
Priority = Impact / Effort
```

Representative action ROI table:

| Action | Effort | Impact (typical) |
|--------|--------|------------------|
| Add CLAUDE.md to a core module | S (30-60 min) | 2-5 min per task × N tasks/week |
| Split a god file (>500 lines) | M (1-3 hr/file) | 30-50% token reduction + accuracy ↑ |
| Add a `## Cross-module deps` section | S (30 min) | prevents cascade bugs |
| Introduce MEMORY.md / ADR | M (2-4 hr upfront) | preserves tribal knowledge (externalized) |
| Add path-validation CI | S (1 hr) | auto-blocks stale references |
| Add an agent eval test | L (4-8 hr) | catches AI regressions |
| Naming refactor | M-L | improves consistency (low priority) |

Sort the top 5 in descending Priority order and present them.
