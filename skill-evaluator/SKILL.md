---
name: skill-evaluator
description: Evaluate an installed Claude Code skill end to end: generate test cases from its own contract, run them in isolated sessions, grade the recorded evidence with independent judges, and report pass/fail per case with cited proof. Use for skill quality, invocation, regression, or before/after comparison of a skill change.
argument-hint: "[skill-name]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion Agent
metadata:
  version: "1.1.0"
  dependencies:
    runtime: "Python >=3.11, uv, authenticated Claude Code with native plugin eval"
---

# Skill Evaluator

Evaluate the named installed skill. Everything runs locally: real Claude sessions in the native `claude plugin eval` sandbox, then separate judge sessions that must cite the recorded evidence line by line. Costs are real model usage (roughly $3 for a quick run, $10–30 for a full run of a skill that spawns agents).

## Three steps

1. **Check the environment once:** `uv run <this-skill>/scripts/evaluate.py doctor`. It reports the CLI version and whether native eval is available; follow its message if something is missing.
2. **Run it:** `uv run <this-skill>/scripts/evaluate.py TARGET --yes`. TARGET is the skill name or the directory containing its `SKILL.md`. Without `--yes` the command stops after generating the test cases so the user can review the table it prints and edit `<skill>/evals/eval_criteria.yaml`; `--yes` accepts them as generated and trusts the target skill's code to run in the sandbox. Add `--allow-tool Write` (and `Edit`, `Bash`, `Agent`) only when the skill's real work needs those tools.
3. **Read the result:** the terminal prints PASS/FAIL per case with a one-line reason, then the report path. `--open` opens `REPORT.html`. Everything the judges cited is under `~/skill-eval/<skill>/<run-id>/`.

## Choosing the size

- `--quick`: 4 standardized cases, one judge session, about five minutes. Use it while iterating on a skill.
- default: 10 cases across invocation, efficiency, best practices, business impact and task completion, one judge session per case.
- `--rigorous`: the same 10 cases graded by three independent judge sessions (median). Use it for a before/after comparison of a skill change.
- `--deep`: 30 cases.

Invocation cases use natural requests without naming the skill, so real routing is tested. Task-completion cases check real files and their hashes, not claims. A case fails on any critical check regardless of its score; the suite passes only when every case passes.

## Comparing before and after

Run the same criteria twice with `--rigorous` (edit the skill in between; pass `--criteria <file>` to reuse the reviewed cases), then `evaluate.py compare RUN_A RUN_B --output compare.html`. The comparison refuses runs whose criteria or evaluator differ. `--resume RUN_DIR` continues an interrupted run; `--regrade RUN_DIR` grades an old run's preserved executions with the current evaluator.

## What to tell the user

Lead with the verdict and the failing cases' reasons, link the report, and separate skill weaknesses from environment errors (a case marked ERROR was not graded). Do not present a judge score as a business result. Details of the case schema, grading rubric and result files are in [references/](references/).
