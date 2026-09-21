# workflow-orchestrator

A small standalone skill for **orchestrator-only** agentic work. One coordinator talks to the user; workers investigate, plan, implement, verify, review and perform authorized delivery. The coordinator manages dependencies and evidence instead of taking over the implementation.

It follows the seminar workflow:

```text
Intake → Context → Plan → Implement → Verify → Review & Land
             ↑                              ↓
             └──── Monitor → lint / rule / eval feedback
```

There are no scripts, hooks, daemon, background supervisor, new state framework, terminal backend or mandatory model in this package. It uses the host's subagents and existing repository tools. Host-native delegation is required; Git worktrees are used for parallel mutating work when applicable. Installing instructions alone does not create these capabilities or enforce an OS sandbox.

## Use it

Install this entire folder through your host's normal skill mechanism. Claude Code commonly discovers a folder containing `SKILL.md` under `.claude/skills/`; other hosts use their own configured skill directories. The workflow's project knowledge is agent-agnostic and follows applicable repository instructions rather than depending on `CLAUDE.md` alone.

Example requests:

```text
Use workflow-orchestrator to orchestrate this feature. Delegate all project work.
Start by understanding the repo, review a plan, implement in isolated workers,
then show separate GATE and VERIFY evidence. Local changes only for now.
```

```text
Use workflow-orchestrator for a read-only Lighthouse baseline across this site's pages.
Have a worker inventory routes and access constraints, a measurement worker
capture repeatable runs, and a reviewer inspect the evidence. Do not change code.
Report the measured opportunities before proposing implementation.
```

For the Lighthouse example, success checks should name page/device/auth state, browser and Lighthouse versions, throttling/cache policy, repetitions, chosen summary and functional constraints. A higher lab score alone does not prove real-user improvement. These are task-specific briefing choices; the skill does not install or assume a Lighthouse runner.

A clear goal starts work immediately. Missing decisions that matter get a short interview. Existing authorization persists; commit, push, merge and deployment follow the exact scope the user/host has already authorized. Read-only measurement does not authorize an optimization change.

The complete workflow and compact worker brief are in [SKILL.md](SKILL.md); reusable delegation and review prompts are in [orchestration-prompts.md](references/orchestration-prompts.md). This package intentionally stays small; it does not claim the original Firstmate distro's supervision, recovery or backend guarantees.

## Version 1.3.0 changes

Three rules were tightened after an evaluated baseline (ten-case suite, real delegated executions): reading any file inside the checkout, including handoff or state documents, is project investigation to delegate; small self-contained changes use a minimum crew and respect the session's turn/time budget by reporting before optional steps; and every landing path names GATE, VERIFY and non-implementer review, without extending commit/push authorization to merge or deployment.

## Verified smoke scope

The records below predate the version 1.2.0 prompt guidance; that guidance has not received an additional live execution test.

The original 2026-09-19 probes below ran under the previous package name `firstmate-lite`; their retained execution records are unchanged.

On 2026-09-19, a real Claude Code session loaded this skill and delegated a four-line read-only fixture investigation to one native Explore worker. The parent used only Skill and Agent calls; only the worker read the project file. The final answer reported the correct line count and labels with quoted line evidence, and the fixture remained unchanged. Frontmatter validation also passed.

A second real session fixed a three-line Python whitespace-normalization function through one implementation worker, then used a different review/verification worker. The parent again used only Skill and Agent calls. The provided two-test suite failed before the change, passed after it, and passed the independent re-run (**GATE**). The independent reviewer separately ran eight direct edge cases including tabs, newlines, empty input and mixed case (**VERIFY**). Only the worker edited the one source line; the provided test file kept its original hash. No commit, merge, deployment or external publication occurred in the fixture.

These bounded probes verify natural loading, delegation, the no-parent-edit boundary, a small local mutation, independent review and separate GATE/VERIFY reporting. They do not establish full production integration, browser verification, parallel-worktree reconciliation, deployment or interruption-recovery guarantees.

After the rename to `workflow-orchestrator`, both bounded probes were repeated through the real Skill tool under the new name. The coordinator again used only Skill and Agent calls. The read-only fixture was unchanged; the mutation fixture passed the original two tests with their original hash preserved, and a separate worker verified seven direct whitespace edge cases. These are regression checks of loading and delegated behavior, not production feature verification.

Inspired by [kunchenguid/firstmate](https://github.com/kunchenguid/firstmate); see the [source revision and MIT notice](THIRD_PARTY_NOTICES.md).
