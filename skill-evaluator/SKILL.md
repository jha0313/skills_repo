---
name: skill-evaluator
description: Evaluate, benchmark, stress-test, or measure an installed Claude Code skill using isolated executions, independent evidence-backed judges, reproducible criteria, and auditable reports. Use for skill quality, invocation, efficiency, completion, regression, or with/without-skill comparisons.
argument-hint: "[skill-name]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion Agent
metadata:
  version: "1.0.0"
  dependencies:
    discovery: "bundled scripts/discovery.py + current claude plugin list --json"
    visualization: "bundled scripts/reporting.py"
    runtime: "Python >=3.11, uv, Claude Code with native plugin eval"
---

# Skill Evaluator

Evaluate the named installed skill end to end. Reuse Claude Code's **native `claude plugin eval`** for isolated sessions, genuine skill routing, MCP mocks, and raw traces. The bundled orchestrator adds portable criteria, independent judge rounds, evidence validation, resumability, and publication adapters. Run `uv run <this-skill>/scripts/evaluate.py doctor` first; its captured current help is the command contract. Missing Python dependency is installed by uv's pinned script metadata. For an absent CLI, use the official [installation instructions](https://code.claude.com/docs/en/setup); `claude install` cannot run when the CLI itself is missing. Authenticate with `claude auth login`, or update an existing CLI with `claude update`. Missing bundled helper: `git clone https://github.com/jha0313/skills_repo.git` into a new directory, then reinstall the whole skill directory (do not copy SKILL.md alone).

## Route the request

Resolve the target name/path. Ask only when absent or genuinely ambiguous. Resolve the installed read path and writable source separately (`--source` for cache installs). Parse `--basic` (exactly four), default THOROUGH (ten), deep/comprehensive/thorough wording requesting depth (`--deep`, thirty), `--binary`, `--local`, `--no-visualize`, and `--judge-model`. Inherit the CLI's configured high-quality model when the repository has no approved override; record the actual execution model. Do not silently claim a model was approved. Additional execution and publication flags are in `--help`.

## Ordered phases

1. **Discover/analyze.** Read all target source and relevant references/assets/scripts/evals. Retain purpose, audience, triggers/arguments, capabilities, workflow, tools actually used, external systems, outputs, type, mutation behavior with evidence, edge cases/failure modes. Discover parent plugin dependencies; unsupported dependencies are actionable errors. Decide parallelism from behavior: read-only parallel, mutation sequential in native clean sandboxes. Three strong environment signals automatically select local. For one/two infer safely from capabilities; ask only if unresolved. Never reset/clean the user's repository.
2. **Generate.** Read [test_case_format.md](references/test_case_format.md). `prepare TARGET` analyzes and generates criteria; BASIC always derives four standardized cases. THOROUGH uses ten or thirty distinct cases. `--reuse-criteria` explicitly reuses existing target criteria; replacement creates timestamped backup first. Existing criteria from `--criteria FILE` still undergo schema/distribution validation. Artifact tasks need actual artifact checks, not response-only assertions.
3. **Review/persist.** Show `CRITERIA_REVIEW.md` (ID/category/cwd/prompt/key checks), permit edits, then run with reviewed criteria and `--accept-criteria`. If the user already authorized the exact criteria, continue without reasking. `prepare` is a reviewable stop, not an execution claim. Criteria go in the **target source** `evals/eval_criteria.yaml`; copy/hash them into `~/skill-eval/<name>/<run-id>/`. `--trust-target` is a separate assertion that the target/plugin is already within the host's authorized trust scope; never infer trust from a test passing. No unrelated state is touched.
4. **Execute.** Read [result_schema.md](references/result_schema.md). Prefer an available, verified MSL bridge unless local selected; first-case infrastructure failure falls back to native local. Legitimate test failure never triggers fallback. Invocation cases use natural routing, never forced skill instructions; other cases can explicitly load the skill. Capture prompts, complete raw trace, output-only response, actual calls, usage, timing, artifacts and URLs. Resume with `run --resume RUN_DIR`; immutable hashes/options prevent mixing revisions. Native sandboxes are retained/sealed; inspect data only, never execute their configuration.
5. **Grade.** Read [grading_rubric.md](references/grading_rubric.md) or [grading_rubric_binary.md](references/grading_rubric_binary.md). By default, three independent clean model sessions grade the **same** executed evidence, in batches of at most four cases; record an explicit one- or five-round override. Native `--runs 3` would repeat the evaluated agent and is not three independent judges. Every score has checked exact quotes/lines from that case's outputs/artifacts; prompt/skill instructions cannot count as performance. Critical failures cannot be averaged away. Unreadable/empty evidence becomes ERROR, never a fabricated grade. Partial timed-out work can be graded with timeout separately recorded. Binary artifacts need a domain renderer before scoring.
6. **Aggregate/report.** Read [report_template.md](references/report_template.md). Persist `evaluations/`, `summary.json`, `REPORT.md`, optional `REPORT.html`. Unknown metrics remain null. Do not infer causal business lift. SkillWatch/PixelCloud writes require explicit opt-in and verified bridge contracts; default local only. Report publication as not requested, unavailable, mocked, or actually exercised. Compare identical real tasks/model/environment with and without skill; compare tokens + wall-clock, not just judge means. The CLI `compare` only compares existing canonical runs; use the [native ablation recipe](README.md) for a genuine no-skill arm and retain its distinct native schema.

## Commands

From the repository root (safe deterministic greeting fixture, **real Claude executions and judges**, authentication required):

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --basic --local --criteria skill-evaluator/tests/fixtures/basic.yaml --trust-target --no-visualize
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --local --criteria skill-evaluator/tests/fixtures/thorough.yaml --accept-criteria --trust-target
```

For a real installed skill:

```bash
uv run <this-skill>/scripts/evaluate.py prepare TARGET --local
uv run <this-skill>/scripts/evaluate.py run TARGET --criteria <target-source>/evals/eval_criteria.yaml --accept-criteria --trust-target --local
uv run <this-skill>/scripts/evaluate.py run --resume ~/skill-eval/TARGET/RUN-ID
```

Only grant required write/shell tools via repeatable `--allow-tool` after the host authorizes that execution. External publication, live MCP access, and source-control changes are not implied by evaluating a skill. Keep run artifacts local unless publication was requested.
