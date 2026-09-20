# Authoring checks and handoff

The canonical schema and formulas live in the sibling **skill-evaluator** package. Resolve and read its `references/test_case_format.md`, selected grading rubric and CLI help. This guide adds authoring decisions, not a second schema.

## Contract map

| Source | Case to derive | Evidence to require |
|---|---|---|
| Description and trigger phrases | Natural positive/negative/ambiguous routing | Actual Skill call, resistance to unrelated requests |
| Argument hint and parsing rules | Missing input, inferred argument, nonexistent target | Appropriate clarification/error or correctly resolved argument |
| Workflow/MUST rules | Happy path plus pressure to skip a required step | Actual sequence and completed outputs |
| NEVER rules | Conflicting instruction or tempting shortcut | Forbidden behavior absent from the complete observed output/tool trace |
| Output contract | Missing/incorrect artifact and realistic happy path | Real file, format/content/domain checks; prose claiming success is insufficient |
| Tool/dependency contract | Expected calls and recoverable failure | Observed runtime names, checked mock fixtures, explicit errors |
| References/examples | Domain-specific edge conditions | The relevant rule is applied to a new example, not copied blindly |

For every proposed case, ask: **What different failure does this catch? Which source rule justifies it? What evidence separates pass from failure?** If two cases have the same answers, merge or replace one.

## Prompt choices

- Knowledge: “Using the release-conventions skill, what should I check before a rollback?” This intentionally makes the skill available and checks its knowledge.
- Invocation: “We need a rollback readiness checklist; what should I look at?” No explicit slash invocation or injected skill content. Make normal routing possible and inspect actual calls.
- Completion: “Create the release checklist for this fixture and save it as release-checklist.md.” Use artifact/tool evidence and authorized isolated execution.
- Negative: a nearby but out-of-scope task where this skill should not be invoked. Set the evaluator's negative invocation expectation, rather than demanding an unnecessary refusal of the user task.

Do not turn every task into a question: task completion must exercise a real deliverable. Do not turn every knowledge check into an imperative: that can start unintended execution.

## Rubrics

Use anchored observable behavior. A good rule might require separating confirmed incident facts from hypotheses and citing the supplied event timestamps. “Be helpful,” “follow best practices,” or “good quality” alone are not scoreable anchors.

Derive lower levels from meaningful failure severity, not a count of decorative words. Mandatory behavior is marked critical. Keep the Likert/binary scale consistent throughout all cases, selected options and report labels. Do not encode the separate 0.0–1.0 team grading convention as an evaluator Likert rubric.

Semantic weighting and the dimension composite are separate evaluator fields. If a missed rule must prevent passing, mark it critical. A large weight by itself does not veto the final dimension verdict.

The evaluator allocates ten cases as 2 invocation /1 efficiency /2 best practices /2 business impact /3 completion. This documented rounding choice cannot satisfy every original percentage range at ten cases. Thirty-case deep mode uses 7/4/7/5/7. BASIC is 1/1/1/1/0. Do not pad the suite with duplicates to satisfy counts.

## Mocks and isolation

Use stable fixture identifiers, synthetic nonsecret data and exact expected calls. Include malformed/missing fields only when the case tests them. A mock that always returns success hides dependency recovery behavior.

Record the source of real MCP runtime names and `input_schema`; a text alias in settings is not tool discovery. Do not invent verification provenance. Unavailable runtime inventory is a reported gap, not permission to run the live service.

Set timeout and turn budgets to actual task needs. For nested evaluator tests, explicitly justify the larger budget and use one bounded fixture; never recursively evaluate the evaluator without a stopping condition. Capture mutation behavior and copied fixtures so that the original working copy remains intact.

## Persistence and review

The target owns `evals/eval_criteria.yaml`. The evaluator's `prepare` command preserves the previous file before replacement and retains a reviewable run copy. For manual refinement, call the existing `core.backup_write` helper in the evaluator's pinned uv/PyYAML environment; it accepts `(path, data)` and creates an exclusive timestamped backup before writing JSON-compatible YAML. Do not implement a second backup helper.

Show ID, category, working directory, exact prompt and key criteria. Include a short mapping from critical checks to target source rules. When publication was not requested, keep all artifacts local. A prepared suite and a schema-valid file are not execution results.

After criteria edits, pass the edited canonical file to a new run. The prepared run's criteria hash remains a truthful record of the earlier version. Do not patch its hash to make a stale run appear reproducible.

## Eval-first and lift

New behavior case → actual intended failure → skill update → same-case pass → old-case regression checks → land. Preserve failed evidence. If the first run fails on authentication or a missing tool, fix the environment before claiming the skill was shown to fail.

A/B needs matching real tasks, initial state, model, tool permissions, mock version and completion criteria. Compare tokens and wall-clock only alongside completed outcome quality. Keep execution variance separate from three independent judges grading one execution. Neither repeated votes nor a prettier rubric establishes a measured productivity increase.
