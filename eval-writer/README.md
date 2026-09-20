# eval-writer

A thin authoring skill for skill evaluation criteria. It reads the target's contracts and helps produce distinct cases, anchored rubrics, tool mocks, backups and a reviewable handoff using the existing **skill-evaluator** framework.

Install the whole `eval-writer/` directory alongside `skill-evaluator/`, or make both available through your normal skill collection. No second runner or judge framework is included.

Example requests:

```text
Write eval cases for my release-checklist skill. Use the default ten-case suite.
Draft a BASIC binary evaluation for this installed skill: /path/to/my-skill.
Stress-test the oncall skill's routing and failure handling with a deep suite.
Export the reviewed cases as JSONL as well as the canonical YAML.
```

A direct CLI equivalent from the repository root is:

```bash
uv run skill-evaluator/scripts/evaluate.py prepare /path/to/my-skill --local
uv run skill-evaluator/scripts/evaluate.py validate /path/to/my-skill/evals/eval_criteria.yaml
```

For BASIC add `--basic` to both commands; for binary add `--binary`; for deep add `--deep`. When evaluating an installed cache copy, add `--source /path/to/writable/skill` to preparation. Exact arguments are verified against the current evaluator help by the skill.

Preparation can use a real model to analyze the skill and generate criteria. It writes the criteria beside the target and preserves a timestamped backup. It does **not** execute or grade the target. The final authoring report links the criteria, manifest, analysis and review table, reports validation and remaining gaps, and gives the next evaluation command.

The executable canonical format is the evaluator's YAML, which may be serialized as JSON. JSONL is an optional exchange export: one complete case per line plus a sidecar preserving defaults/mode/provenance. Raw JSONL is not passed to the YAML-only validator.

Read [SKILL.md](SKILL.md) and the [authoring guide](references/authoring-guide.md). The authoritative schema and scales remain in [skill-evaluator](../skill-evaluator/README.md). Schema-valid criteria do not prove the skill works; an actual red/green run and with/without comparison provide different evidence.

## Authoring smoke evidence

On 2026-09-19, a real Claude Code session selected `eval-writer` from a natural-language authoring request and called the existing evaluator author on a temporary Harbor release-brief skill. It produced ten target-specific cases (2/1/2/2/3 categories, 25 distinct semantic questions), covering natural/negative routing, source IDs, unknown kinds, breaking migration, authentication review, injected change text, missing version and missing input file.

The first generated Likert draft incorrectly used binary anchors in 11 critical checks. The invalid draft was retained, the exact bytes were backed up with the evaluator helper, and those anchors were repaired without changing the source rules or case prompts. The current evaluator CLI then reported `Criteria valid`. This was **not** an automatic single-pass success. The target was not executed or graded; routing, author generation, repair/backup and schema validation are the verified scope.
