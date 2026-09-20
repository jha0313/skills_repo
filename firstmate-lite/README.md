# firstmate-lite

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
Use firstmate-lite to orchestrate this feature. Delegate all project work.
Start by understanding the repo, review a plan, implement in isolated workers,
then show separate GATE and VERIFY evidence. Local changes only for now.
```

```text
Use firstmate-lite for a read-only Lighthouse baseline across this site's pages.
Have a worker inventory routes and access constraints, a measurement worker
capture repeatable runs, and a reviewer inspect the evidence. Do not change code.
Report the measured opportunities before proposing implementation.
```

For the Lighthouse example, success checks should name page/device/auth state, browser and Lighthouse versions, throttling/cache policy, repetitions, chosen summary and functional constraints. A higher lab score alone does not prove real-user improvement. These are task-specific briefing choices; the skill does not install or assume a Lighthouse runner.

A clear goal starts work immediately. Missing decisions that matter get a short interview. Existing authorization persists; commit, push, merge and deployment follow the exact scope the user/host has already authorized. Read-only measurement does not authorize an optimization change.

The complete workflow and compact worker brief are in [SKILL.md](SKILL.md). This package intentionally stays small; it does not claim the original Firstmate distro's supervision, recovery or backend guarantees.


## Verified smoke scope

On 2026-09-19, a real Claude Code session loaded this skill and delegated a four-line read-only fixture investigation to one native Explore worker. The parent used only Skill and Agent calls; only the worker read the project file. The final answer reported the correct line count and labels with quoted line evidence, and the fixture remained unchanged. Frontmatter validation also passed.

A second real session fixed a three-line Python whitespace-normalization function through one implementation worker, then used a different review/verification worker. The parent again used only Skill and Agent calls. The provided two-test suite failed before the change, passed after it, and passed the independent re-run (**GATE**). The independent reviewer separately ran eight direct edge cases including tabs, newlines, empty input and mixed case (**VERIFY**). Only the worker edited the one source line; the provided test file kept its original hash. No commit, merge, deployment or external publication occurred in the fixture.

These bounded probes verify natural loading, delegation, the no-parent-edit boundary, a small local mutation, independent review and separate GATE/VERIFY reporting. They do not establish full production integration, browser verification, parallel-worktree reconciliation, deployment or interruption-recovery guarantees.

## Source and design scope

Inspired by [kunchenguid/firstmate](https://github.com/kunchenguid/firstmate), inspected at commit [`90cd351ac8b828d7074fe4a432acda246355bec7`](https://github.com/kunchenguid/firstmate/tree/90cd351ac8b828d7074fe4a432acda246355bec7) on 2026-09-19. The reference describes a coordinator with delegated workers, isolated workspaces, bounded task briefs, supervision and faithful outcome reporting. Its full product is an agent distro, not a standalone copyable orchestration skill.

This is an independently written simplification, with the requested Context/Plan/Implement/GATE+VERIFY/Review+Land/feedback workflow. It does not copy the original runtime, internal skills, nautical persona, helper commands, registry, merge policy or lifecycle machinery. It is not an official Firstmate release or a claim of identical behavior.

The upstream reference is MIT-licensed. Its copyright/permission notice is retained below for attribution and any adapted instructional substance:

```text
MIT License

Copyright (c) 2026 Kun Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
