# Evidence-backed Likert grading

Each score is 1 Failure, 2 Major gaps, 3 Acceptable, 4 Good with minor gaps, 5 Excellent. Use the case's anchored semantic rubric. Match observable behavior, not writing style unless style is the contract. Record matched rubric level, exact supporting quote, case output/artifact path and line range. Every score needs evidence. Missing evidence is not an automatic 3.

Five dimensions:

1. Invocation: correct trigger, false-positive resistance and argument parsing. Inspect actual Skill calls; loading instructions later is not a natural invocation test.
2. Efficiency: proportional tokens/tools/latency, useful batching/parallelism and appropriate model. A tiny task not spawning agents is often excellent. Unknown metrics remain unknown, never zero.
3. Best practices is the mean of context_management, subagent_architecture, tool_selection, skill_design, process_adherence, error_handling_safety. Judge applicability to this actual case; no unnecessary subagent penalty for simple work.
4. Business impact is the mean of time_saved, scale_potential, quality_ceiling, problem_difficulty, productivity_revenue_link. Score demonstrated deliverable usefulness/plausible pathway. Do not claim measured saved time, revenue or causal productivity from a hypothetical example; bounded uncertainty is good practice. A simple task has a limited ceiling/difficulty.
5. Task completion: requested end-to-end deliverable exists and works. A claim or passing lint alone is insufficient; inspect artifacts and domain checks.

THOROUGH/deep composite = invocation×.10 + efficiency×.10 + best_practices×.15 + business_impact×.15 + task_completion×.50. BASIC is the equal mean of its four dimensions. Pass at >=3.0 only if all critical requirements pass. Letter thresholds use unrounded numbers: A >=4.50, B >=3.50, C >=3.00, D >=2.00, F >=1.00. Round for display only.

Each semantic question contributes score×weight / sum(weights). A critical question below 3, a required-present miss, forbidden hit, missing required artifact, or wrong routing fails the case even if the composite is high. The report preserves the score and separately marks `critical_failure`; do not erase diagnostic information. Aggregate pass rate counts ERROR as not passed and distinguishes failed cases from infrastructure errors.

Three separate judge processes see the same citable execution evidence (final response, structured tool calls, metadata, artifact manifest and captured artifacts); the raw transcript is retained on disk for audit but is not sent to judges. A round whose citations fail verification is retried once in a fresh session, with the invalid attempt's raw output retained; a second failure is an infrastructure ERROR for that batch. Use median score per criterion (ordinal analogue of majority; preserves the middle anchored level). Each original judge vote and evidence remains in JSON. Judge consensus does not eliminate bias. Author/judge are separate sessions from the evaluated agent.

Transcript parsing: preserve raw JSONL and complete conversation, but **response checks use only assistant final output**, tool checks use actual structured tool-use events, artifact checks use real copied files/hash. Synthetic skill content, prompt and criteria cannot substantiate execution. Citations from another case, missing files, wrong lines and fabricated quotes are rejected. Metadata citations support efficiency/infrastructure, not answer correctness.

An unreadable/effectively empty transcript produces infrastructure ERROR (no numeric score). A timeout with substantive work is graded on that work, with `timed_out: true`; unfinished deliverables still fail completion. Nonempty error messages do not prove work. Every relevant artifact must be read; unsupported binary outputs require a domain renderer rather than a guessed grade.

## Scoring layers and reporting

Each case has a primary **category**, but judges score every dimension selected by the run mode for that executed case. The primary category controls suite coverage and category breakdowns; it is not the only dimension graded. Best-practice and business-impact dimensions are recomputed from their six/five subcriteria after votes.

The semantic weighted score is a separate diagnostic field. It does not silently replace the documented dimension composite. Mark required semantic behavior `critical: true` when failing it must fail the case; an unmarked semantic gap can lower its diagnostic score without overriding an otherwise passing composite. Judge dimension anchors should reflect relevant case-specific behavior as well.

The suite's `score` is the mean composite of scored cases. `pass_rate` counts passed cases divided by all cases, including infrastructure errors. The implementation's suite `verdict` requires every case to PASS; this conservative suite policy is stricter than the **per-case** composite >=3 threshold. A high mean/letter grade can therefore coexist with a FAIL suite. Preserve both and show the failing IDs.

No numeric score is assigned to infrastructure ERROR. If a required artifact is missing but the response/tool trace contains substantive evidence, the case can receive diagnostic scores while its deterministic artifact check forces FAIL. Failed requirements should not be hidden by smoothing or rounding.
