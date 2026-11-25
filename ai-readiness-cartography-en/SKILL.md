---
name: ai-readiness-cartography-en
description: Deprecated since 2026-11. Merged into ai-readiness-cartography, which now has English output (--lang en).
disable-model-invocation: true
license: MIT
metadata:
  version: "2.1.0"
---

# Deprecated: use `ai-readiness-cartography`

Since 2026-11 the English edition is part of [`ai-readiness-cartography`](../ai-readiness-cartography/). This folder holds only this notice. No scorer or template is left here.

If the user calls this skill, do not score anything. Tell them it moved and give these commands:

```bash
npx skills add jha0313/skills_repo --skill ai-readiness-cartography
npx skills remove ai-readiness-cartography-en
```

Then use `ai-readiness-cartography` with `--lang en`. The English steps are in its `references/SKILL.en.md`. Do not install or remove anything unless the user says so. Scores from the old edition (rubric v2) are not comparable with the new ones (v2.1).
