/skill-creator Build a Skill that scores how AI-ready a codebase is. It audits an arbitrary git repository against the AI-Ready rubric (100 pts, 7 categories) and produces a JSON scorecard + an English HTML dashboard + an ROI-ranked action list. Create the scoring rubric file and the Python scoring script.

Improved AI-Ready Codebase Rubric, 100 pts
Category	Points	What It Measures
A. AI Navigation & Coverage	15	Can the AI quickly find the whole codebase/modules/workflows
B. Context Document Quality	20	Do context files follow the "compass, not encyclopedia" principle
C. Tribal Knowledge Externalization	20	Are hidden rules, failure patterns, and human-only knowledge structured
D. Cross-Module Dependency & Data Flow Mapping	15	Can the AI trace the blast radius of a change
E. Verification & Quality Gates	15	Is there a system to verify AI-generated context and code changes
F. Freshness & Self-Maintenance	10	Is context auto-maintained so it doesn't go stale
G. Agent Performance Outcomes	5	Is real AI task success rate/efficiency improvement measured
A. AI Navigation & Coverage, 15 pts
Score	Criteria
0	The AI has to grep/search the repo directly and guess at its structure
5	Some major modules have a README/context
10	Most core modules have their role, entry point, related files written down
15	Every core module/workflow has an AI navigation guide. "Where do I look?" is findable within 1-2 hops
Recommended measurement:

Navigation Coverage = core modules reachable via AI context / total core modules
Module/workflow coverage matters more than file count.

B. Context Document Quality, 20 pts
Item	Points	Full Score Criteria
B1. Conciseness	4	25-35 lines or roughly ~1,000 tokens
B2. Quick Commands	4	Copy-paste-able commands and when to use them
B3. Key Files	4	The 3-5 key files actually needed for edits
B4. Non-Obvious Patterns	4	Failure-causing hidden rules and exceptions stated
B5. See Also / Cross References	4	Links to related modules, context files, dependency maps
What matters here is not "lots of documents" but only task-relevant context.

C. Tribal Knowledge Externalization, 20 pts
Score	Criteria
0	Knowledge lives only in a senior engineer, Slack, past PRs
5	Some gotchas scattered across READMEs or comments
10	Some tacit knowledge of recurring work is documented
15	Compatibility rules, naming conventions, generated-code rules, deprecated-but-required rules are written down
20	Most identified tribal knowledge is reflected in context files/checklists/playbooks, and the AI can retrieve it via query
It's good to use Meta's Five-Question Framework directly as the scoring criteria.

For each module, 4 points each if you can answer these 5 questions, 20 total:

What does this module configure/own?
What are common modification patterns?
What non-obvious patterns cause failures?
What are the cross-module dependencies?
What tribal knowledge is hidden in comments/history/human memory?
D. Cross-Module Dependency & Data Flow Mapping, 15 pts
Score	Criteria
0	Change blast radius is traced manually by a human
5	Some architecture diagrams or dependency notes exist
10	Dependencies and ownership between major modules are documented
15	"What depends on X?" can be answered with a graph/index/map. Can trace how a change propagates across repo/service/test/data flow
This item is especially important in large-scale codebases. The core problem in the Meta case was also that "one field change creates a ripple effect across six subsystems."

E. Verification & Quality Gates, 15 pts
Item	Points	Full Score Criteria
E1. Reference Accuracy	5	0 hallucinations of file paths, APIs, commands
E2. Independent Critic Review	4	At least 2-3 rounds of independent review or a checklist
E3. Task Validation	4	Provides build/test/lint/typecheck/e2e verification commands per change type
E4. Prompt/Workflow Tests	2	Representative AI task queries are actually tested
The Meta article's "zero hallucinated paths" is great to emphasize in a talk. AI-readiness is not "documents that are nice for AI to read" but verified context infrastructure.

F. Freshness & Self-Maintenance, 10 pts
Score	Criteria
0	Context is managed manually and staleness is unknown
3	There's a doc owner and occasional updates
6	CI or scripts detect some broken paths/references
10	File-path validation, coverage-gap detection, critic review, and stale-reference repair run automatically on a schedule
This item deserves more emphasis than the original rubric gave it. As Meta puts it, stale context can be more dangerous than no context.

G. Agent Performance Outcomes, 5 pts
Score	Criteria
0	No measurement of AI performance improvement
2	Qualitatively "it helps"
3	Representative task success rate or human intervention rate is measured
5	tool calls, token usage, task completion time, correctness, prompt pass rate, etc. measured before/after
Example metrics:

- AI task pass rate
- average tool calls per task
- average tokens per task
- human clarification count
- failed PR/rework rate
- hallucinated file path count
- time-to-first-correct-change
Final Grade
Score	Level	Meaning
90-100	AI-Native / Agentic-Ready	Agent autonomously handles most recurring work, and the context layer is self-maintaining
75-89	AI-Ready	AI can navigate, edit, and verify reliably for most development work
60-74	AI-Assisted	AI is useful but complex/domain-specific tasks need human context
40-59	AI-Fragile	Simple tasks work, but high error risk from hidden rules and dependencies
<40	AI-Hostile	Heavy reliance on tribal knowledge, and AI works from guesses
