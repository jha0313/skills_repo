# Binary grading

Use **PASS/FAIL**, stored 1/0. Never show Likert numbers or letter grades in binary verdict displays. Per-dimension scores are binary; aggregate means are explicitly pass rates. Raw rubric_level equals 0 or 1 and every decision cites direct evidence. The JSON dimensions retain numeric values for analysis and include dimension_verdicts for display.

Invocation, efficiency and completion pass only when their documented observable requirements hold. Best practices passes at **4 of 6** subcriteria (context_management, subagent_architecture, tool_selection, skill_design, process_adherence, error_handling_safety). Business impact passes at **3 of 5** (time_saved, scale_potential, quality_ceiling, problem_difficulty, productivity_revenue_link). Applicability matters; do not invent revenue or saved time. For a simple task, absence of subagents may pass architecture.

BASIC passes at **3/4 dimensions**; THOROUGH/deep at **4/5**. Composite is dimensions passed / dimensions evaluated (a pass rate). Critical checks must all pass; required-present misses, forbidden hits, missing artifacts or wrong invocation fail regardless of composite.

Semantic score = sum(weight × 0-or-1) / sum(weights); each rubric has exactly 0 and 1. Each critical semantic check must pass. Three independent judge rounds grade identical evidence; majority decides every underlying binary criterion. Best-practice/business thresholds apply after voting, not by averaging categorical labels.

Quote exact case-local response/tool/artifact evidence with line numbers. Prompt, loaded skill instructions, criteria or another case never count. Missing/empty transcripts are ERROR with score null; failures use FAIL, not a letter. Timed-out substantive work can be graded with timeout metadata. Missing required artifact fails even if the agent claims success. Infrastructure ERROR is separate from legitimate FAIL and does not trigger a false positive fallback.

HTML/Markdown use verdict badges, dimension PASS/FAIL, pass rates and evidence links. Unknown cost/tokens are unknown. Preserve every independent raw judgment; majority is a stability measure, not ground truth.

## Two different pass rates

`score` for one case is the fraction of its selected dimensions that pass. `semantic_score` is the weighted fraction of its semantic checks that pass. The latter is diagnostic; mark a mandatory semantic check `critical: true` to make its failure veto the case. The suite's `pass_rate` is the fraction of **cases** whose final verdict is PASS, counting ERROR in the denominator. Label these rates distinctly.

The suite's final `verdict` requires all cases to PASS. This does not change the per-case BASIC 3/4 or THOROUGH 4/5 dimension thresholds. An aggregate dimension value between 0 and 1 is a cross-case pass rate, not an individual nonbinary verdict. Keep original judge decisions and apply 4/6 and 3/5 subcriterion thresholds only after majority voting.
