# ai-readiness-cartography-en (지원 종료 · Deprecated, 2026-11부터)

영어판은 [`ai-readiness-cartography`](../ai-readiness-cartography/)에 합쳤다. 이 폴더에는 안내만 남아 있다.
The English edition is now part of [`ai-readiness-cartography`](../ai-readiness-cartography/). Only this notice is left here.

```bash
npx skills add jha0313/skills_repo --skill ai-readiness-cartography   # 대신 이것 · use this
npx skills remove ai-readiness-cartography-en                         # 옛 것 지우기 · remove the old one
```

- 영어 출력 · English output: `python3 -I <ai-readiness-cartography>/scripts/score.py REPO --lang en` (`<ai-readiness-cartography>`는 새 스킬을 설치한 폴더 · the folder where the new skill is installed)
- 영어 안내 · English guide: `ai-readiness-cartography/references/SKILL.en.md`
- v2 점수와 v2.1 점수는 비교할 수 없다. · v2 and v2.1 scores are not comparable.

`SKILL.md`의 `disable-model-invocation`은 Claude Code가 이 안내를 새 스킬보다 먼저 부르지 않게 하려고 쓴다(규격 밖 필드라 claude.ai 업로드는 안 된다).
