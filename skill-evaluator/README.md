# skill-evaluator

An auditable Claude Code skill-evaluation orchestrator. It discovers a skill, prepares portable criteria, delegates execution to the installed Claude Code native eval runner, grades preserved evidence in independent judge sessions, and writes linked local reports.

The local path is implemented over `claude plugin eval`, rather than a second agent execution framework. MSL Judge, SkillWatch and PixelCloud require an operator-supplied bridge based on those services' current help/schema. Their names in this package are not evidence of a working internal-service connection.

## Install and check the environment

Keep this entire `skill-evaluator/` directory together: `SKILL.md` depends on its scripts and references. From a checkout of [jha0313/skills_repo](https://github.com/jha0313/skills_repo), install through your normal Claude Code skill mechanism, or copy the whole directory into `~/.claude/skills/skill-evaluator` when that destination does not already exist. Do not overwrite an existing installation without preserving its changes. The CLI examples below also work directly from the repository root without installing the skill.

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/), and an authenticated Claude Code version whose native eval help exposes the required flags. `uv run` installs the pinned `PyYAML==6.0.3` dependency in an isolated environment. Bare `python3` needs that dependency installed separately.

```bash
uv run skill-evaluator/scripts/evaluate.py doctor
```

If Claude Code is absent, follow the official [installation instructions](https://code.claude.com/docs/en/setup). If present but missing native eval capabilities, run `claude update`, then `claude plugin eval --help`. Authenticate with `claude auth login`. The development environment exposed Claude Code 2.1.275 on 2026-09-19; compatibility is checked at startup, not inferred from that historical version.

A missing bundled discovery/report helper means the package is incomplete: obtain a fresh checkout with `git clone https://github.com/jha0313/skills_repo.git` into a new directory and reinstall the complete skill folder. These helpers replace the unavailable internal template-discovery and visualization dependencies.

## Two smoke commands

Run from the repository root. These use the included small greeting fixture, real agent executions and independent judges; they consume the authenticated account's normal model usage. They do not call SkillWatch or PixelCloud.

BASIC, exactly four cases:

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --basic --local --criteria skill-evaluator/tests/fixtures/basic.yaml --trust-target --no-visualize
```

Default THOROUGH, ten cases, local HTML enabled:

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --local --criteria skill-evaluator/tests/fixtures/thorough.yaml --accept-criteria --trust-target
```

`--trust-target` asserts that this target and any parent-plugin code are already within the host user's authorized trust scope. It does not grant Bash, Write/Edit, network tools, live MCP, or publication. Read the fixture and criteria before using that assertion. `--accept-criteria` records the host decision to execute the presented criteria; it is not a substitute for reviewing unknown criteria.

A failed skill case exits 1. Configuration, infrastructure or publication errors exit 2. An interrupted process exits 130 and retains checkpoints. Exit 0 means the completed suite passed; `prepare` and `validate` also exit 0 without evaluating a skill, so read the command and report state.

## Evaluate an installed skill

```bash
uv run skill-evaluator/scripts/evaluate.py prepare TARGET --local
```

Use a unique installed name or the exact directory containing `SKILL.md`. Pass `--source /path/to/writable/skill` when the installed read path is a plugin cache. The tool writes criteria beside the **target** source, with a timestamped backup before replacement, and prints a review table. It does not reset or clean the source working copy.

After reviewing/editing those criteria:

```bash
uv run skill-evaluator/scripts/evaluate.py run TARGET --local --criteria /path/to/writable/skill/evals/eval_criteria.yaml --accept-criteria --trust-target
```

Or resume the unchanged prepared run after review:

```bash
uv run skill-evaluator/scripts/evaluate.py run --resume ~/skill-eval/TARGET/RUN-ID
```

Resume uses persisted options, criteria and hashes; do not add new evaluation flags. Changes to the skill, evaluator, criteria or adapter configuration require a new run. Completed case execution and valid judge checkpoints are reused.

## Modes and controls

| Control | Behavior |
|---|---|
| `--basic` | Exactly 4 cases: invocation, efficiency, best practices, business impact. No dedicated task-completion case. |
| No size flag | Default THOROUGH: 10 cases across all 5 dimensions. |
| `--deep` / `--comprehensive` | 30 cases. In conversational use, explicit “thorough/deep/comprehensive” depth requests route here; there is no separate `--thorough` CLI flag. |
| `--binary` | PASS/FAIL grading with weighted binary semantic checks. Default is Likert 1–5. |
| `--local` | Bypass any configured MSL bridge and use native local isolation. |
| `--no-visualize` | Skip HTML and PixelCloud; keep Markdown/JSON and optional SkillWatch. |
| `--model MODEL` | Select evaluated-agent model. |
| `--judge-model MODEL` | Select independent author/judge model. Without an approved repository default, inherit the authenticated CLI default and record it. |
| `--concurrency N` | 1–8; default 3. Mutation behavior forces sequential case execution. |
| `--judge-rounds N` | 1, 3 or 5; default 3. These grade the same execution evidence in independent sessions. |
| `--timeout SECONDS` | Evaluated-session default, 300; per-case override wins, maximum 3,600. |
| `--judge-timeout SECONDS` | Per author/judge process limit, default 300, maximum 3,600. |
| `--allow-tool TOOL` | Repeatable explicit grant for tools needed by the authorized task. |
| `--reuse-criteria` | Reuse existing target criteria explicitly; BASIC still needs the standardized four-case suite. |
| `--config FILE` | Opt-in operator bridge definitions with current contract provenance. |

Discovery analyzes actual mutation behavior. Read-only cases can run concurrently; mutating skills execute sequentially in native clean sandboxes. Invocation uses normal skill discovery in a fresh session. Explicitly loading skill context is allowed only for other categories and is recorded as such.

See [case schema and mocking](references/test_case_format.md), [Likert rubric](references/grading_rubric.md), [binary rubric](references/grading_rubric_binary.md), [result/bridge schemas](references/result_schema.md), and [report contract](references/report_template.md).

## What is saved

Default run location: `~/skill-eval/<skill-name>/<run-id>/`.

- `manifest.json`, `analysis.json`, `criteria.yaml`, `CRITERIA_REVIEW.md`, captured native CLI help.
- `cases/TC-001/`: prompt, complete transcript, native trace, output-only response, actual tool calls, metadata, artifacts, normalized execution and adapter logs.
- `judges/`: independent raw judge inputs/results (every attempt retained; an invalid round is retried once in `…-retry-N`) and per-round validated checkpoints.
- `evaluations/TC-001.md` and `.json`: exact evidence citations, matched rubric levels and deterministic check results.
- `summary.json`, `REPORT.md`, optional `REPORT.html`: totals, breakdowns, failures, recommendations and evidence links.

Unknown usage/cost is null. CLI cost estimates are not invoices. Agent cost, judge cost and criteria-author cost are retained separately; inspect `author_cost_usd` as well as execution/judge totals. Sum of case durations is not elapsed wall-clock when cases run concurrently.

A case's primary category is its coverage label. Judges still score every selected dimension for that execution. The semantic weighted score is diagnostic; `critical: true` makes a mandatory semantic failure override an otherwise passing dimension composite. The suite's final verdict is conservative: every case must pass. Read scores, failed requirements and infrastructure errors together.

## A/B: demonstrate added value

The orchestrator's `compare RUN_A RUN_B` compares two existing canonical runs; add `--output FILE.html` to render a local paired dashboard (pass/fail per case, category and dimension deltas, environment fingerprint, and evidence links for every non-passing case) with `scripts/compare_report.py`. It does **not** run a no-skill arm automatically, and matching criteria hashes alone do not prove that the model, fixtures, tools or environment match.

For real with/without execution, reuse the native runner's current ablation support. Prepare a trusted native plugin eval case with a neutral task prompt, identical fixtures and domain graders. Do not force the skill name/body in the baseline; do not use only the orchestrator's nonempty-output capture grader as a quality measurement. From a directory where the named output paths are appropriate:

```bash
claude plugin eval /path/to/trusted-plugin --ablation with-without --runs 3 --concurrency 1 --mocks record --no-publish --keep-temp --json ab-result.json --output-dir ab-results
```

This command runs three evaluated-agent attempts per arm, not three independent judges of one transcript. It uses the native plugin's own grader schema and native aggregate format, distinct from this orchestrator's canonical result schema. Keep both arms' raw traces, apply the same evidence-backed domain criteria, and compare completion, tokens and wall-clock. A native report is not accepted directly by `compare` without a verified canonical translation.

Do not claim measured time savings, revenue or causal productivity from a rubric's business-impact score. Fix the task, starting revision, model/budget, mocks and completion threshold; repeat or vary ordering to inspect variance. A lower token count caused by incomplete work is not efficiency lift.

## Internal services and publication

Default runs are local. `--publish-skillwatch` and `--publish-pixelcloud` require separate opt-in and a configured bridge. Project creation additionally requires `--create-project`. Bridges must preserve host authorization, validate the real service schema, and enforce the run ID as an idempotency key. The package deliberately does not guess private service endpoints or `fbcode//msl/judge:run_eval` flags.

MSL preference/fallback is available through the normalized bridge interface. A configured MSL first-case infrastructure error can retry through local execution; a legitimate failed skill case is not grounds for changing adapters. Real MSL/SkillWatch/PixelCloud integration must be reported separately from deterministic mock bridge tests.

## Explicit deviations and limits

- Ten cases cannot satisfy all requested percentage ranges as integer counts: the largest allowed counts sum to nine. Default allocation is **2/1/2/2/3**, prioritizing completion at 30%; deep uses **7/4/7/5/7**, meeting the stated ranges.
- No approved high-quality judge model was configured in this repository. The CLI default is inherited unless selected explicitly; that is recorded rather than called “repository approved.”
- Bundled discovery and HTML helpers replace absent internal discovery/visualization tools. Internal services use operator bridges; an interface and mocked contract do not establish live integration.
- Nontext artifacts require a domain-specific renderer before judgment; the generic judge does not claim to inspect images, PDFs or executable behavior from filenames or binary bytes.
- Mocked tool inputs make dependencies reproducible, not the LLM itself deterministic. Three judge rounds reduce one kind of variation; they do not establish truth or eliminate shared bias.
- Generic sandbox execution cannot guarantee an arbitrary plugin works unchanged. Unsupported dependencies require a materialized environment or a clear error, not a fabricated score.

Validation results belong to a specific code revision and retained run. Read the final run's manifest and report before describing a skill as successfully evaluated.

## Verification recorded during development

On 2026-09-19, with Claude Code 2.1.275:

- 31 deterministic regression tests passed, including cancellation, criteria backups, exact distributions, prompt/cross-case evidence rejection, missing/modified artifacts, publisher idempotency, binary thresholds, and bounded schema repair.
- Ruff lint/format and mypy passed. The repository workflow repeats deterministic checks on relevant pull requests and pushes; it does not require paid model credentials.
- Real BASIC Likert evaluation passed 4/4 cases; real default THOROUGH passed 10/10. Each execution was independently judged three times. Their CLI-estimated execution/judge costs were about $2.21 and $5.42 respectively, not invoices or estimates for arbitrary skills.
- Natural-language routing invoked `skill-evaluator` itself through the real Skill tool in a read-only explanation request.
- Real native Bash PreToolUse interception returned a canned marker without executing the original command. Real native MCP stand-in executed one exact mocked lookup with no unmocked calls. Both tests were fixtures, not live external-service operations.
- SkillWatch publication was exercised only through a deterministic fake bridge; MSL Judge and PixelCloud live integration were not exercised.

An initial live run exposed fractional derived-dimension validation, and initial criteria authoring exposed mixed binary/Likert critical rubrics. Invalid output was retained as an infrastructure error instead of scored; derived dimensions are now recomputed centrally and authoring permits one logged, bounded schema-only repair. Passing fixture runs establish the exercised orchestration paths, not correctness for every installed skill or artifact domain.
