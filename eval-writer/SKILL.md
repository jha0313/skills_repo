---
name: eval-writer
description: Write, improve, or validate reproducible evaluation cases for an installed agent skill. Use when drafting skill evals, test scenarios, anchored rubrics, negative routing cases, or mocked tool fixtures before evaluating or changing a skill. Produces reviewed criteria and an execution handoff; does not equate schema validity with a passing skill evaluation.
argument-hint: "[skill-name] [--basic|--deep] [--binary]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion
metadata:
  version: "1.0.0"
  dependencies:
    evaluation-framework: "skill-evaluator/scripts/evaluate.py and its references/test_case_format.md"
    runtime: "uv, Python >=3.11, authenticated Claude Code with native plugin eval"
---

# Eval Writer

Turn the target skill's actual contracts into distinct, reproducible evaluation cases. Reuse **skill-evaluator's `prepare` and `validate` commands**, schemas, backup logic and source discovery. Do not build a separate runner, judge, score formula or publisher. This skill authors criteria; running the target requires an execution request or an existing authorization to evaluate it.

## Resolve the target and dependency

1. Resolve the named installed skill or exact `SKILL.md` directory. Ask only when it is absent or genuinely ambiguous. Read applicable repository instructions and the target's complete entrypoint plus relevant references/scripts/assets/existing evals.
2. Find `skill-evaluator/scripts/evaluate.py` beside this skill in the same collection, or under an actual installed skill/plugin root. Use filesystem discovery; do not invent an absolute home or assume a plugin namespace. Read the evaluator's **current** `references/test_case_format.md` and CLI `--help`.
3. If the dependency is missing, stop with: `git clone https://github.com/jha0313/skills_repo.git` into a new directory, then install the complete `eval-writer` and `skill-evaluator` folders together. Do not overwrite an existing installation. If the CLI dependency check fails, follow its actionable setup/update error.
4. Separate installed read path and writable source (`--source`). Never persist another skill's criteria under the eval-writer or evaluator framework directory. The target being evaluated may legitimately be either skill itself.

## Resolve authoring options

- Default: THOROUGH, ten cases. `--basic`: four standardized categories. `--deep` / `--comprehensive`, or an explicit expanded “deep/thorough/comprehensive” request: thirty.
- `--binary`: anchored 0/1 checks and PASS/FAIL. Otherwise use evaluator Likert 1–5. The seminar's separate team-scoring rule (critical failure→0, quality .5–1) is **not** this schema.
- Forward `--source`, `--judge-model`, `--judge-timeout`, `--output` when supplied. The author uses the evaluator's independent author model; do not claim a repository-approved model if none exists.
- Fresh criteria by default. `--reuse-criteria` only when explicitly requested. Resolve relative CLI paths from the recorded working directory.

## Author in this order

### 1. Extract a contract map

For each meaningful target rule, identify the source path/section, expected observable behavior, a plausible failure, and which evidence can distinguish them. Include trigger/argument handling, MUST/NEVER rules, artifact outputs, tool requirements and dependency errors. Classify actual mutation behavior; a Bash permission alone is not proof of mutation.

Read [authoring-guide.md](references/authoring-guide.md) for the quality checklist and knowledge/invocation distinction. Keep cases tied to different real contracts rather than repeating one “follow instructions” check.

### 2. Prepare with the existing framework

Use the discovered evaluator path. This generates criteria, analyzes behavior, creates a timestamped backup before replacing existing target criteria, retains a manifest and emits a review table. It does **not** execute or grade the target.

```text
uv run <evaluator>/scripts/evaluate.py prepare <target-read-path> --local [--source <target-source-path>] [--basic|--deep] [--binary]
```

Angle-bracket values and bracketed options above are notation, not shell text to paste. Omit size flags for default THOROUGH. Inspect the generated `analysis.json`, target `evals/eval_criteria.yaml`, and `CRITERIA_REVIEW.md` before declaring authoring complete.

### 3. Review and refine

Check category allocation, distinct behaviors, grounded rubrics, required artifacts, explicit timeout, and mock coverage against the source. Before **any further criteria overwrite**, use the evaluator's `core.backup_write` helper; do not bypass the backup just because `prepare` already made one. Keep revisions in the target source and include the corresponding backup path in the authoring report.

Invocation prompts must exercise genuine natural routing: positive, negative, ambiguous and argument inference where the case budget permits. Do not use slash invocation, injected skill instructions, or forced context. Other knowledge tests should mention the skill and ask a question such as “What conventions should I follow when…?”; real task-completion tests should request the actual deliverable. A knowledge answer cannot prove artifact completion.

Only require literal text when the contract truly needs it. Prefer observable semantic questions with case-specific anchors. Each mandatory condition is `critical: true`; unmarked semantic checks are diagnostic in this evaluator. In a Likert suite, **critical checks still require all five 1–5 anchors**: critical failure means a score below 3, not a separate 0/1 rubric. Do not mix binary critical anchors into Likert criteria. Never weaken a failing criterion merely to obtain a passing result.

For interception, require mock data. Validate exact MCP runtime tool names and input schema against an actual inventory; never guess from config aliases. If that inventory is unavailable, report the unresolved dependency and the evidence needed; do not mark invented names as verified. Unknown live calls must be blocked or explicitly unsupported by the runner. Mocking external responses does not make model output deterministic.

### 4. Validate and hand off

```text
uv run <evaluator>/scripts/evaluate.py validate <target-source>/evals/eval_criteria.yaml [--basic|--deep] [--binary]
```

Use the same mode/scale as authoring. Schema validation is necessary but does not review semantic quality or prove the target works. Present the compact ID/category/cwd/prompt/key-criteria table and permit edits. Existing authorization can cover execution after review; otherwise end with a concrete prepared result and the exact execution command, without claiming an eval pass.

Preserve the immutable prepared run. After editing criteria, start a **new** evaluation using `--criteria <edited-file> --accept-criteria`; do not edit its run manifest or resume stale criteria. Reuse an unchanged prepared run only after its exact criteria are reviewed.

For YAML/JSONL exchange, the canonical executable file is the evaluator's YAML (JSON is also valid YAML). If JSONL is requested, export one complete case per line, materializing inherited `working_directory`, and retain the top-level defaults/mode/source hash in a sidecar. Revalidate the canonical YAML; do not pass raw JSONL to a CLI that currently accepts YAML. This is a format export, not a second evaluation format or engine.

## Final authoring report

Return paths to criteria, analysis/review table, timestamped backup, optional JSONL/sidecar; state mode, scale and case allocation. Summarize distinct covered contracts, gaps, mock provenance and validation performed. Explicitly state **target evaluation not run** when only authoring occurred.

Give the exact next `run` command based on current CLI help and the selected target/mode. Only include `--trust-target` when trust is already within the user's authorized scope; only grant required tools. Explain eval-driven use: run new cases and confirm the intended failure → update skill → rerun unchanged criteria → inspect regressions → land. Failure caused by broken infrastructure is not the intended red phase.

For claimed improvement, compare the same task, model, starting state, completion threshold and mock environment with/without the skill; measure tokens and wall-clock. Repeated independent judge rounds reduce variance, not shared bias. Do not put invented result scores or business uplift into authored criteria.
