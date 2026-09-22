# skill-evaluator

Evaluate a Claude Code skill the way you would review a colleague's work: give it real tasks, watch what it actually does, and have independent judges grade the recorded evidence. Everything runs locally on top of Claude Code's native `claude plugin eval` sandbox.

## Install

Keep the whole `skill-evaluator/` directory together (the scripts and references belong to `SKILL.md`). Install it through your normal Claude Code skill mechanism, or copy the directory to `~/.claude/skills/skill-evaluator`. The commands below also work from a checkout of [jha0313/skills_repo](https://github.com/jha0313/skills_repo).

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/), and an authenticated Claude Code whose native eval is available. Check once:

```bash
uv run skill-evaluator/scripts/evaluate.py doctor
```

## Use

```bash
# 4 cases, one judge, about five minutes — while you iterate on a skill
uv run skill-evaluator/scripts/evaluate.py my-skill --yes --quick

# 10 cases, one judge per case — the default
uv run skill-evaluator/scripts/evaluate.py my-skill --yes

# 10 cases, three judge sessions per case (median) — for before/after comparisons
uv run skill-evaluator/scripts/evaluate.py my-skill --yes --rigorous --allow-tool Write
```

`my-skill` is an installed skill name or the directory that contains its `SKILL.md`. The run prints a review table of the generated cases, executes them, grades them, and ends with one line per case:

```text
FAIL: 9/10 cases passed, grade B, ~$28.85 (CLI estimate), 43 min
  TC-001  PASS  4.67  Natural routing for a read-only delegation
  ...
  TC-010  FAIL  3.33  Resume with an unverified PASS claim
                          protected file changed: STATE.md
Report: ~/skill-eval/my-skill/<run-id>/REPORT.md  (HTML: .../REPORT.html)
```

`--yes` accepts the generated cases and states that the target skill's code may run in the sandbox. Leave it off to stop after the table, edit `<skill>/evals/eval_criteria.yaml`, and run again with `--criteria <that file> --yes`. Add `--allow-tool` for each tool the skill's real work needs beyond Read, Glob, Grep and Skill. `--open` opens the HTML report. Exit code 0 means every case passed, 1 means a case failed, 2 means an infrastructure error left a case ungraded, 130 means interrupted (`--resume RUN_DIR` continues).

## What a run does

1. **Analyze** the skill's own files and write ten cases (four with `--quick`, thirty with `--deep`) that test what it promises: two natural-language invocation cases (one that should trigger it, one that should not), one efficiency case, two best-practice cases, two business-impact cases, three task-completion cases with real files. Existing criteria are backed up before being replaced.
2. **Execute** each case in a fresh native sandbox with a copy of the skill and the fixture files. The transcript, final answer, every tool call (with who made it: the session itself or a delegated worker), produced files and their hashes are saved.
3. **Grade** in separate judge sessions that see only the recorded evidence, never the prompt or the skill text. Every score must cite a file and line; citations are verified and a round whose citations do not hold is discarded and retried once. Three rounds (`--rigorous`) are combined by median.
4. **Report** `REPORT.md`, `REPORT.html`, `summary.json` and one evaluation file per case, all linking to the evidence.

A case fails on any critical check (a required file missing, a protected file changed, a critical rubric question below 3/5, wrong routing) whatever its composite score. The suite passes only when every case passes.

## Options

| Option | Effect |
|---|---|
| `--quick` | 4 cases, 1 judge session, concurrency 4 |
| `--rigorous` | 3 judge sessions per case |
| `--deep` | 30 cases |
| `--binary` | PASS/FAIL rubrics instead of 1–5 |
| `--yes` | accept generated criteria and trust the target |
| `--criteria FILE` | run reviewed or hand-written criteria |
| `--allow-tool T` | extra tool for the evaluated session (repeatable) |
| `--model`, `--judge-model` | pin the evaluated and judge models; otherwise the CLI default is used and recorded |
| `--concurrency N` | parallel cases (1–8, default 3); each case has its own sandbox. `--sequential` runs one at a time for skills that touch shared external resources |
| `--timeout`, `--judge-timeout` | seconds per evaluated session / judge session |
| `--open` | open `REPORT.html` when done |
| `--resume RUN_DIR` | continue an interrupted run with its saved options |
| `--regrade RUN_DIR` | grade a run's preserved executions with the current evaluator |
| `compare RUN_A RUN_B --output FILE.html` | before/after dashboard for two runs with identical criteria |

## Before/after comparison

Run the skill with `--rigorous`, change it, run again with the same `--criteria` file, then `compare`. The comparison refuses runs whose criteria or evaluator hash differ, and it is observational: same criteria, model and fixtures make the pass/fail changes interpretable; the composite score differences of a few hundredths are within judge noise.

## Limits

Judges are models: three agreeing rounds reduce variance, not shared bias. The same skill can score differently on a rerun. Business impact is a rubric judgment, not a measured outcome. Non-text artifacts (images, PDFs) are not judged without a domain renderer. Costs shown are CLI list estimates, not invoices. The sandbox cannot guarantee that an arbitrary plugin works unchanged; missing dependencies produce an error, never a guessed score.

See [references/test_case_format.md](references/test_case_format.md) for the case schema and mocks, [grading_rubric.md](references/grading_rubric.md) for the rubric, [result_schema.md](references/result_schema.md) for the files a run leaves behind, and [report_template.md](references/report_template.md) for the report contract.
