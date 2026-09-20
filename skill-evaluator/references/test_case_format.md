# Portable criteria, generation and mocks

The canonical file is `TARGET/evals/eval_criteria.yaml`. JSON documents are valid YAML 1.2 and are written by the helper to preserve exact prompts. Never place another skill's criteria in this evaluator. Before replacement, create `eval_criteria.yaml.backup-<UTC timestamp>` exclusively. The run keeps an immutable copy and hash.

Use a top-level portable `default_working_directory` (`.` or `~/...`) and required `test_cases`. The current validator defaults an omitted directory to `.`. Precedence: case working_directory > top-level default > `.` (empty isolated sandbox). Explicit relative directories resolve from target source and are copied as data by a trusted, evaluator-owned scaffold; never execute user project configuration. No user-specific `/Users/name` or `/home/name` paths in reusable criteria. `target_skills` uses repository-relative SKILL.md paths.

```yaml
default_working_directory: .
test_cases:
  - id: TC-001
    name: Greeting routing
    category: invocation
    project: observatory-greeting
    target_skills: [observatory-greeting/SKILL.md]
    working_directory: .
    prompt: How does the Observatory team greet new contributors?
    description: Tests normal discovery using a natural request.
    expected_behavior: Invokes the greeting skill and supplies the exact team convention.
    eval_target: all
    expect_invocation: true
    timeout_seconds: 120
    max_turns: 8
    quality_criteria:
      required_present: [Welcome to Observatory.]
      required_absent: []
      semantic_checks:
        - question: Did the agent supply the documented greeting accurately?
          weight: 3
          critical: true
          rubric:
            5: Exact greeting and appropriate concise context.
            4: Correct greeting with a minor irrelevant addition.
            3: Correct greeting with usable explanation.
            2: Greeting convention incomplete.
            1: Wrong or absent greeting.
      artifact_checks: []
```

Binary checks use **only** `rubric: {1: "Observable PASS anchor", 0: "Observable FAIL anchor"}`; weights stay positive. Every case has at least one anchored semantic check. Optional `critical: true` requires binary 1 or Likert >=3; failures gate the final verdict. `required_present`/`required_absent` are literal **output** constraints: only semantically essential text belongs there. For `eval_target: response`, scan assistant final output; tool_usage scans actual calls; artifact scans captured files; all combines them. Never scan user prompt or synthetic loaded instructions as output.

`artifact_checks: [{path: result.md}]` requires a real captured file, not a claimed link. Missing artifacts fail. Nontext artifacts require an audited domain renderer before judging; binary bytes are not silently decoded as meaningful proof.

Modes and integer allocation (`invocation / efficiency / best_practices / business_impact / task_completion`):

- BASIC: **1/1/1/1/0**, exactly four.
- THOROUGH: **2/1/2/2/3**, exactly ten. The requested percentage bounds have no ten-case integer solution (max total is nine); the extra case goes to task completion, making it 30%.
- Deep/comprehensive: **7/4/7/5/7**, thirty, all requested percentage ranges satisfied.

Invocation prompts use natural language, never `/skill-name`, forced context, or answer leakage. Include positive, negative (`expect_invocation: false`), ambiguous and argument-inference cases as the budget permits. Other categories can use `forced_context: true` (default) to load the skill normally. Distinct task-completion scenarios cover happy path, missing/nonexistent targets, complex input, pressure/conflicting instructions, artifacts and recoverable dependency errors. Ten cases cannot dedicate one task-completion case to every scenario; spread scenarios across categories and use deep mode for full coverage.

## Mock contracts

`intercept_patterns` is a list of **full-match** Bash regular expressions. `mock_data[pattern]` has stdout, stderr, exit_code. A native PreToolUse hook replaces only matching Bash inputs with shell-quoted canned stdout/stderr and the requested exit code; the original command never executes. Unmatched commands are denied with `UNMOCKED_EXTERNAL_CALL`. A harmless randomized-marker probe first verifies that the current runner honors hooks; if it fails, the live case is refused. Canned response strings never execute as shell code. A missing capability is not a passing mock test.

`intercept_mcp_tools` contains exact verified runtime names (`mcp__server__tool`). Each corresponding mock_data object contains response, input_schema, description, optional expect and error, and `runtime_name_verified: true` with the inventory provenance in `runtime_name_source`. Obtain names/schemas from actual tools/list, never infer from aliases. The adapter compiles native `evals/mocks/<server>/<tool>.md` and `_tools.json`; real servers are withheld (`--mocks record`, never `--allow-real-servers`). A runtime mismatch/error is an infrastructure failure. Mock data is mandatory whenever interception is configured.

Optional `analysis` beside test_cases supplies reviewed behavior analysis for reused criteria: all the discovery fields plus `mutates: true|false` and mutation_evidence. Unknown behavior is not assumed read-only. Generated author analysis is retained separately.

Use knowledge questions for context tests ("What conventions should I follow when using skill X?"). Use execution requests for genuine artifact/task completion tests. Mention the skill for behavior tests, omit forced routing for invocation tests. Fix environment/model/criteria for A/B comparison. Three judge rounds reduce instability; they do not prove unbiased or correct judgments. Nested evaluator tests use a justified 900-second timeout and a bounded fixture, never recursive unbounded self-evaluation.

## Field reference

The values below describe the portable file accepted by `validate_criteria`, not the native runner's different case schema. The adapter translates it into native cases.

| Field | Type / default | Contract |
|---|---|---|
| `default_working_directory` | string, default `.` | Prefer an explicit value in published criteria. `.` means an empty isolated sandbox, not the caller's checkout. |
| `test_cases` | nonempty list | Exact category allocation for the selected mode; IDs are unique. |
| `analysis` | optional object | Reviewed discovery analysis for criteria reuse. Include `mutates` as a boolean and mutation evidence; otherwise preparation runs an author analysis. |
| `id` | string | `TC-` and three digits, e.g. `TC-001`. |
| `name` / `description` | strings | Human-readable behavior and what distinguishes this case. |
| `category` | enum | `invocation`, `efficiency`, `best_practices`, `business_impact`, `task_completion`. |
| `project` | string | Target skill's frontmatter name; routing checks compare observed Skill calls to it. |
| `target_skills` | list of relative paths | At least one path; no absolute path or `..`. Record the actual repository-relative `SKILL.md` location. The run target remains the single skill resolved by discovery. |
| `working_directory` | optional string | Overrides the portable default; explicit directories are copied as fixture data. Source checkout is not reset, switched, or cleaned. |
| `prompt` | nonempty string | Exact evaluated input. A natural invocation prompt contains no slash command or forced skill body. |
| `expected_behavior` | string | Observable result, including important failure behavior. |
| `eval_target` | enum | `response`, `artifact`, `tool_usage`, or `all`; determines which actual outputs support content checks and citations. |
| `expect_invocation` | boolean, default `true` | Invocation only: a negative case uses `false`. |
| `forced_context` | boolean | Must not be true for invocation. Other categories default to asking the normal session to use the installed skill. |
| `timeout_seconds` | integer, default runner limit | 1–3,600 seconds; nested tests require an explicit justified budget. |
| `timeout_reason` | optional string | Explain elevated nested-test timeouts; retained as criteria provenance. |
| `max_turns` | integer, adapter default 15 | Limit the evaluated native session; use a small positive budget appropriate to the task. |
| `quality_criteria` | object | Four required arrays: `required_present`, `required_absent`, `semantic_checks`, `artifact_checks`. |
| `semantic_checks[].question` | nonempty string | A directly scoreable, observable question. |
| `semantic_checks[].weight` | positive finite number | Used in the separately reported weighted semantic score. |
| `semantic_checks[].rubric` | map | Exactly integer keys 1–5 for Likert or 0/1 for binary. Each value is a behavior anchor. |
| `semantic_checks[].critical` | boolean, default `false` | Failure forces the case verdict to FAIL, regardless of dimension composite. |
| `artifact_checks[].path` | relative string | Required captured artifact, no traversal. Additional domain checks belong in semantic rubrics or a verified renderer. |
| `artifact_checks[].sha256` | optional 64-hex string | Expected SHA-256 of the captured file. A mismatch is a deterministic critical failure; use it for protected files that must remain byte-for-byte unchanged. Existence alone is not preservation. |
| `intercept_patterns` | optional list of regex strings | Full-match Bash interceptions, with matching entries in `mock_data`. |
| `intercept_mcp_tools` | optional list of runtime names | Exact, inventory-verified `mcp__server__tool` names. |
| `mock_data` | optional mapping | Required for any interception. Do not put secrets or live credentials in fixtures. |

A scalar working-directory example using `~/project/fixtures` is portable between homes only when the same fixture is provisioned there. It does not guarantee equal fixture contents; record the input/environment version when comparing runs.

## Binary case example

This is one case to include in a four-, ten-, or thirty-case suite; running it alone fails the intentional category-count validation.

```yaml
id: TC-001
name: Greeting routing
category: invocation
project: observatory-greeting
target_skills: [observatory-greeting/SKILL.md]
prompt: How does the Observatory team greet new contributors?
description: Validate natural routing and the greeting contract.
expected_behavior: Calls the target skill and answers with its documented greeting.
eval_target: all
expect_invocation: true
quality_criteria:
  required_present: [Welcome to Observatory.]
  required_absent: []
  semantic_checks:
    - question: Does the response give the documented greeting?
      weight: 3
      critical: true
      rubric:
        1: The greeting is supplied accurately.
        0: The greeting is wrong or absent.
    - question: Is the explanation limited to the requested convention?
      weight: 1
      rubric:
        1: The answer stays relevant and concise.
        0: The answer adds unrelated procedures or tasks.
  artifact_checks: []
```

## Bash mock fragment

Append to a case that actually needs this one command. It is an isolated fixture, not a live CLI contract.

```yaml
intercept_patterns:
  - 'teamctl status --json'
mock_data:
  'teamctl status --json':
    stdout: '{"state":"ready"}\n'
    stderr: ''
    exit_code: 0
```

For MCP, derive `input_schema` from the actual runtime `tools/list`. A syntactically plausible name or `runtime_name_verified: true` typed without evidence is not verification. Preserve the inventory source in `runtime_name_source` and inspect tool-call traces after execution.
