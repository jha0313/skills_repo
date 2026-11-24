# Agent skills I use every day

[한국어](README.md) · [Changelog](CHANGELOG.md) · MIT

When you hand work to an AI agent, three jobs stay with you: **understanding it, verifying it, and choosing what to look at next.** These skills shrink those three jobs. The skills are written in Korean; the agent answers in your language when you ask.

```bash
npx skills add jha0313/skills_repo            # pick what you need
npx skills add jha0313/skills_repo --skill into
```

Claude Code plugin: `/plugin marketplace add jha0313/skills_repo` → `/plugin install silbal@silbal`

| Group | Skill | What it does |
|---|---|---|
| Understand | [into](into/README.md) | Turns a PR, repo, paper, video, thread or skill into a short, fixed format per source type: eli5, ste, html, interactive, doc, slides, test, shorts, video |
| Delegate | [chief-of-staff](chief-of-staff/README.md) | One session runs many projects and shows you the three things to look at now |
| Delegate | [workflow-orchestrator](workflow-orchestrator/README.md) | Runs one task end to end through delegated research, planning, building, verification and review |
| Verify | [codex-review](codex-review/README.md) | Sends a review to another vendor's model and acts only on findings that were confirmed |
| Verify | [skill-evaluator](skill-evaluator/README.md) | Runs a skill in isolated sessions and grades each case with evidence |
| Verify | [eval-writer](eval-writer/README.md) | Writes the evaluation criteria first |
| Verify | [skills-lint](skills-lint/README.md) | Finds spec violations, overlaps and broken links in installed skills |
| Tidy up | [time-convert](time-convert/README.md) | Time zones, weekdays and time left, computed by a script |
| Tidy up | [disk-cleanup-analyzer](disk-cleanup-analyzer/README.md) | macOS disk usage report that protects AI session folders |
| Tidy up | [improve-token-efficiency](improve-token-efficiency/README.md) | Tokens and cost per project from your session logs |
| Prepare a repo | [ai-readiness-cartography](ai-readiness-cartography/README.md) | Scores how ready a repository is for agents and draws a map (`--lang en`) |

Deprecated (stub only): `presentation_slides` → [visualize](https://github.com/careerhackeralex/visualize) or `into slides`; `ai-readiness-cartography-en` → `ai-readiness-cartography --lang en`.
