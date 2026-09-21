# Canonical results and bridge contracts

Normalized execution, per-case evaluations, manifests and aggregates use `schema_version: skill-evaluator/1`. Raw tool/CLI responses and leaf metadata/artifact files retain their own shapes. Both adapters cross `normalize_execution`; external bridges must translate their **verified** internal output to this contract, never guess Meta field names. This repository/environment provides no MSL Judge, SkillWatch schema or PixelCloud upload contract. They are not installed or claimed to work here. Current native CLI help/source (Claude Code 2.1.275, inspected 2026-09-19) provides reusable local isolation, routing, mocks and raw output.

## Execution contract

```json
{"conversation":"complete transcript", "response":"assistant final output only", "tool_calls":[{"name":"Skill","input":{"skill":"plugin:example"}}], "metadata":{"model":"actual model","started_at":"ISO8601","finished_at":"ISO8601","duration_seconds":1.2,"exit_state":"completed","timed_out":false,"usage":{"input_tokens":100,"output_tokens":20,"cache_read_input_tokens":0,"cache_creation_input_tokens":0},"cost_usd":null,"cost_basis":"unavailable","skill_invocations":["plugin:example"]},"artifacts":{"files":[{"path":"report.md","exists":true,"sha256":"...","evidence_path":"cases/TC-001/artifacts/report.md","content":"actual file text"}],"urls":[]}}
```

Unknown counters/costs are null. An adapter creates every cited file in the run case directory; path traversal/symlinks are rejected. MSL output without sufficient raw trace/artifact evidence is ERROR. `response` never includes user prompts or synthetic instructions. Native transcript source `out/trace.jsonl` is copied, not private runtime config. Kept native `sealed/home/cwd` is opened only for data inspection and resealed; never execute git, hooks or config there. URLs recovered from transcript are labeled mentions, not verified reachable publications.

Case storage: `cases/TC-ID/conversation.txt`, `trace.jsonl` (native), `prompt.json`, `response.txt`, `tool_calls.json`, `metadata.json`, `artifacts.json`, `artifacts/*`, `execution.json`, raw adapter stdout/stderr/JSON. Per-case result: `evaluations/TC-ID.json` and `.md`.

Evaluation JSON: case_id/name/category, grading, status (`graded|error`), score (null on infrastructure error), verdict (`PASS|FAIL|ERROR`), optional Likert grade, critical_failure, dimensions, binary dimension_verdicts, six best_practice_subcriteria, five business_impact_subcriteria, semantic checks/weighted score, deterministic hits/misses/forbidden/artifact/routing checks, raw judge_rounds, metadata, judge cost/allocation, evidence links. Every judgment score has rubric_level, reason, and `evidence:[{path,line_start,line_end,quote}]`. Paths are case-local output/artifact allowlists; exact quote/line validation runs before scoring.

Manifest: evaluator_version, run_id, created_at, state, skill (installed/source paths, revision, content hash), complete analysis, criteria_hash, timestamped backup path, resolved options, adapter config/hash/provenance, CLI help/version, execution_adapter, pricing configuration, author usage, per-case state and publication receipt/status. States: criteria_review→executing→grading→reported→complete/incomplete; interruption preserves checkpoints. Atomic writes and per-run lock prevent duplicate runners. Resume rejects changed source, criteria, evaluator or bridge config and reuses successful execution/judge checkpoints. A regrade run (`run --regrade RUN_DIR`) copies a source run's executions into a new run graded by the current evaluator and records `regrade_of`: source run_id, path, evaluator_hash_at_execution, imported_cases, pending_cases.

Aggregate `summary.json`: total/passed/failed/errors/pass_rate, score/distribution, category and dimension breakdowns, best-practice breakdown, cost/token/duration totals, known-cost subtotal, author cost, failure clusters, recommendations tied to IDs, per-case results. CLI cost is a **list-price estimate**, not a bill. Execution and judge costs are separate; shared judge batch costs are allocated equally and raw batch usage retained. Null component totals remain null.

## Verified internal bridges (optional)

Config JSON maps `msl`, `skillwatch`, `pixelcloud` to:

```json
{"command":["/absolute/path/to/your-verified-bridge"],"contract_provenance":"current internal --help and schema source, revision/date"}
```

A bridge executable receives one JSON stdin request and returns one JSON stdout response, no shell interpolation. Timeouts are bounded, stdout/stderr/request/response retained. Host installation/auth is operator-owned. Validate the real `fbcode//msl/judge:run_eval` help and SkillWatch/PixelCloud accepted schemas **inside the environment that has them**; then implement the small translation. A configured fake bridge is only a test fixture.

MSL operation `execute`: request includes schema_version, operation, run_id, case, analysis, options; response `{"status":"ok","execution":<canonical above>}`. A first-case infrastructure error falls back once to native local, retaining reason. A legitimate failed result remains a failed test. No MSL bridge configured means native local immediately.

Publish operation: request includes run_id, idempotency_key=run_id, summary, report_path, create_project flag. Response requires `{"status":"ok","idempotency_key":"same run id","url":"..."}`. Only opt-in `--publish-skillwatch`/`--publish-pixelcloud` calls it. Project creation needs `--create-project` and must be idempotent in the bridge. Receipt caches payload hash; repeated identical run does not republish. Bridge/server must enforce the key for uncertain network outcomes as well. Changed published summary requires a new run. Failures remain visible, never logged as success. `--no-visualize` skips local HTML/PixelCloud, retains local Markdown/JSON and optional SkillWatch.

## Verification boundaries

Native runner MCP mocks are its accepted directory schema, not invented Meta intercept flags. Bash mocks require a verified native PreToolUse hook capability probe and block unknown commands. Direct live MCP services and unbounded live Bash are never needed for default fixtures. Parent-plugin context cannot silently be stripped: external plugin-local scripts/delegated components need a supported materialized snapshot or an actionable dependency error. Binary artifact judging needs a renderer.

## Field-level schemas

These are the normalized, versioned records maintained by the evaluator. Consult retained native JSON for provider-specific details; do not discard that evidence when translating an adapter.

### `execution.json` and case evidence

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | `skill-evaluator/1`. |
| `conversation` | string | Complete captured conversation/trace text, including input provenance. Not itself an allowed correctness citation. |
| `response` | string | Actual evaluated assistant output; never criteria or injected skill text. |
| `tool_calls` | array | Structured observed tool calls with name and input, optionally native IDs. |
| `metadata.model` | string or null | Actual executed model when reported, not an invented requested-model identity. |
| `metadata.started_at`, `finished_at` | timestamps | Recorded execution boundaries. |
| `metadata.duration_seconds` | number | Per-case observed execution duration. |
| `metadata.exit_state`, `timed_out` | string, boolean | Completion/error and timeout state are distinct from judge verdict. |
| `metadata.usage` | object | Input/output/cache-read/cache-creation token counters; unavailable counters are null. |
| `metadata.cost_usd`, `cost_basis` | number or null, string | Provider estimate and its provider/version provenance; not actual billing. |
| `metadata.adapter` | string | Normalizing adapter identity. |
| `metadata.skill_invocations` | array of strings | Observed Skill-tool invocations used for routing checks. |
| `metadata.permission_denials`, `error`, `mock_status` | optional provider data | Keep permission/mock/infrastructure failures visible. |
| `artifacts.files` | array | Captured paths and existence, content/hash/bytes/evidence path when present, or missing-file error. |
| `artifacts.urls` | array | URLs and provenance. Transcript mention does not establish reachability or successful publication. |

An artifact's `path` is its sandbox-relative produced path; `evidence_path` is run-relative. `artifacts/*` contains copied bytes. A filename claimed in a response is not a captured artifact. File size caps, symlink refusal and renderer limitations produce explicit failure rather than silently skipping required proof.

### `evaluations/TC-001.json`

| Field | Type | Meaning |
|---|---|---|
| `case_id`, `name`, `category` | strings | Stable criteria identity and coverage category. |
| `grading` | enum | `likert` or `binary` on scored cases. |
| `status` | enum | `graded` or `error`. |
| `score` | number or null | Dimension composite; infrastructure errors have no score. |
| `verdict` | enum | `PASS`, `FAIL`, `ERROR`. |
| `grade` | optional string | Likert only: A/B/C/D/F by unrounded score. |
| `critical_failure` | boolean | Any mandatory content, semantic, routing or artifact failure vetoes passing. |
| `dimensions` | mapping | Four BASIC or five THOROUGH/deep dimension values. |
| `dimension_verdicts` | binary-only mapping | PASS/FAIL labels for each dimension. |
| `best_practice_subcriteria` | mapping | Six voted values, used to derive best-practices dimension. |
| `business_impact_subcriteria` | mapping | Five voted values; empirical and inferred effects remain distinguished in evidence/reasons. |
| `semantic_checks` | array | Index, voted score and weight. |
| `semantic_score` | number | Separate weighted diagnostic; mandatory checks still veto. |
| `checks` | object | Required-present hits/misses, forbidden hits, missing artifacts and routing failure. |
| `judge_rounds` | array | Every full validated independent judgment, including citations. |
| `metadata` | object | Preserved normalized execution metadata. |
| `judge_cost_usd`, `judge_cost_allocation` | optional | Known batch cost allocated to cases with the allocation method recorded. |
| `evidence` | object | Run-relative transcript and artifact-manifest links. |
| `error` | error-only string | Infrastructure reason. Do not invent ordinary dimension fields for unscored errors. |

A judge entry has `{score, rubric_level, reason, evidence}`; semantic entries additionally carry `index`. `evidence` is a nonempty array of `{path, line_start, line_end, quote}`. The validator checks exact quotation and line bounds, rejects path escapes and other-case evidence, and limits output sources according to `eval_target`. A reason alone never substitutes for a quote.

### `manifest.json`

- Identity: `schema_version`, `evaluator_version`, `run_id`, `created_at`, `state`.
- Skill: `name`, `description`, `installed_path`, `source_path`, source `revision`, content `skill_hash`; retain parent-plugin snapshot provenance when applicable.
- Inputs: complete behavior `analysis`, `criteria_hash`, `criteria_backup`, resolved `options`, `options_hash`, `behavior_hash`, `evaluator_hash`.
- Execution: dependency/version discovery, `execution_adapter`, adapter `config`, `config_hash`, optional `msl_fallback_reason`.
- Accounting: `pricing_configuration` and author usage. Requested model and resolved execution model are separate facts.
- Checkpoints: `cases` indexed by ID, with `pending`, `executed`, `graded`, or `error`, plus recorded failure information. Judge checkpoints retain validated case IDs and raw round usage.
- Publication: each requested destination's status/receipt or error; unrequested writes are explicit. A completed evaluation can still have a publication error—read publication status and CLI exit status.
- Deviations: explicit changes from the requested contract, including integer allocation and unavailable internal integrations.

CLI options are resolved once. Resume validates immutable hashes and refuses to combine revisions. A successful execution can be regraded after an interrupted judge without rerunning the evaluated skill. Changing criteria requires a new run rather than editing a manifest to defeat the checks.

### `summary.json`

- Identity/mode: `schema_version`, `run_id`, `mode`, `grading`.
- Outcome: `total`, `passed`, `failed`, `errors`, case `pass_rate`, mean scored-case `score`, suite `verdict`, optional Likert `grade`, `score_distribution`.
- Breakdowns: `categories` with count/pass_rate, `dimensions`, six `best_practice_subcriteria`. Binary aggregate dimension values are rates, not single-case verdicts.
- Accounting: `duration_seconds` is a sum of case durations; `tokens` stores known input/output/cache totals; `execution_cost_usd`, `judge_cost_usd`, `cost_usd`, `known_cost_subtotal_usd`; criteria-author cost is separately `author_cost_usd` and included in `cost_usd`; `execution_and_judge_cost_usd` preserves the subtotal. `wall_clock_seconds` is elapsed execution/grading including resumed downtime.
- Diagnosis: `failure_clusters`, recommendations tied to `case_id`, and complete normalized `results`.

The suite `verdict` requires every case to pass. It is distinct from the per-case 3.0 Likert / binary dimension thresholds and from a mean grade. Null totals must not be converted to zero. Where a duration or token total excludes author/judge work, label that scope. A dashboard comparing runs must preserve criteria/model/environment differences instead of presenting unmatched runs as measured causal lift.

Native staging always selects one case with `--eval-dir skill-evaluator-cases --case TC-ID` and verifies exactly one matching returned name, even when a parent plugin defines its own experimental.evals directory. Parent plugin name, sibling scripts/assets, and declared dependencies are snapshotted; the complete plugin snapshot hash participates in resume validation.

Before grading, reusing, or rendering a completed score, verify persisted response/transcript/metadata/artifact/evaluation hashes. Missing or modified evidence refuses reuse; do not silently rerun it under the old score.
