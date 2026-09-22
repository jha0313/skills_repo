# Report contract

Write `REPORT.md`, `summary.json`, every `evaluations/TC-ID.md/.json`; optional `REPORT.html` is self-contained. Local reports always exist, including infrastructure failures. Never present a mocked run as a real agent score.

Report sections: skill purpose, execution mode/grading, executive grade (Likert) or PASS/FAIL badge (binary), total/pass/fail/error/pass-rate, what was tested, category/dimension/six best-practice breakdowns, token/duration/cost totals, failure clusters/missing requirements, actionable recommendations with motivating IDs, audit/provenance links.

HTML includes metric cards (pass rate/case count/mode/tokens/duration/cost), What this skill does / What we tested / How it turned out, sortable per-case table (ID/name/category/score-or-verdict/tokens/cost/evidence), collapsible prompt/check/quote/artifact evidence, and complete raw-data footer. Every row links to its evaluation and transcript. Use semantic headings, accessible table controls, responsive overflow, escaped untrusted text, print styling. Scores never stand alone without evidence links.

Binary labels are PASS/FAIL and pass rates; no letter grades or 1–5 score display. Literal source text in raw audit evidence may mention other grading modes; do not rewrite evidence to conceal it. Likert letter thresholds use raw values. Unknown cost is not zero. All costs identify CLI list estimates and include judge cost separately. Run elapsed duration and sum of case durations differ under concurrency; label them correctly.

Recommendations target specific failing checks/IDs, not vague "improve quality". Business impact is a bounded rubric assessment; A/B with identical task/model/criteria/mock environment is required before claiming lift, and judge lift does not establish causal financial gain.

Anti-patterns: score-only reports, prompt-text-as-performance, fabricated excerpts, unclickable/missing artifacts, stale source mixed during resume, binary letters, zero for missing usage or unlabeled fixtures.
