# 실밸개발자가 매일 쓰는 에이전트 스킬

> AI에게 일을 맡기면 세 가지가 남는다. **이해하기, 확인하기, 다음에 볼 것 고르기.** 이 저장소는 그 세 가지를 줄이는 스킬이다.

[English](README.en.md) · [변경 기록](CHANGELOG.md) · [기여](CONTRIBUTING.md) · MIT

```bash
npx skills add jha0313/skills_repo            # 골라서 설치
```

Claude Code 플러그인으로도 된다: `/plugin marketplace add jha0313/skills_repo` → `/plugin install silbal@silbal`

**2분 안에 해 보기**

| 설치 | 물어본다 | 이렇게 답한다 |
|---|---|---|
| `npx skills add jha0313/skills_repo --skill time-convert` | 서울 2026-11-25 오후 2시가 런던으로 몇 시야? | 2026-11-25(수) 05:00 — 스크립트가 계산한다 |
| `npx skills add jha0313/skills_repo --skill into` | `into eli5 <PR·저장소·글 주소>`, 그다음 `into interactive` | 한 화면 그림, 그다음 눌러 보는 화면 |

## 어떤 때 쓰나

### 이해한다 — "에이전트가 잘했다는데 무슨 말인지 모르겠다"

| 스킬 | 한 줄 | 확인한 것 |
|---|---|---|
| [into](into/README.md) | PR·저장소·논문·영상·글·스킬을 유형마다 정해진 틀로 짧게 바꾼다: eli5 · ste · html · interactive · doc · slides · test · shorts · video · 전문가 과정 | {{INTO_EVIDENCE}} |

### 맡긴다 — "세션이 열 개인데 뭘 먼저 봐야 하지"

| 스킬 | 한 줄 | 확인한 것 |
|---|---|---|
| [chief-of-staff](chief-of-staff/README.md) | 여러 프로젝트를 비서실장 세션 하나에 맡기고, 오늘 볼 것 3개만 받는다 | 테스트 55개 |
| [workflow-orchestrator](workflow-orchestrator/README.md) | 한 작업을 조사·계획·구현·검증·리뷰로 나눠 끝까지 위임한다 | 행동 평가 사례 10개 |

### 검증한다 — "통과했다는데 정말?"

| 스킬 | 한 줄 | 확인한 것 |
|---|---|---|
| [codex-review](codex-review/README.md) | 다른 회사 모델에게 리뷰를 맡기고, 돌아온 지적을 확인한 뒤에만 반영한다 | 테스트 35개(가짜 codex) |
| [skill-evaluator](skill-evaluator/README.md) | 스킬을 격리된 세션에서 돌려 사례마다 근거와 함께 채점한다 | 테스트 45개 |
| [eval-writer](eval-writer/README.md) | 스킬의 평가 기준을 먼저 쓴다 | skill-evaluator로 검사 |
| [skills-lint](skills-lint/README.md) | 설치된 스킬의 규격 위반·겹침·깨진 링크를 찾는다 | 테스트 32개 |

### 매일 정리한다 — "또 이거"

| 스킬 | 한 줄 | 확인한 것 |
|---|---|---|
| [time-convert](time-convert/README.md) | 시간대·요일·남은 시간을 머리로 세지 않는다 | 테스트 32개 |
| [disk-cleanup-analyzer](disk-cleanup-analyzer/README.md) | 맥 용량을 나눠 보여 주되 AI 세션 작업 폴더는 지키게 한다 | 테스트 62개 |
| [improve-token-efficiency](improve-token-efficiency/README.md) | 세션 기록으로 프로젝트별 토큰·비용을 본다 | 테스트 48개 · 가격 확인 2026-11-24 |

### 저장소를 준비한다 — "에이전트가 자꾸 헤맨다"

| 스킬 | 한 줄 | 확인한 것 |
|---|---|---|
| [ai-readiness-cartography](ai-readiness-cartography/README.md) | 에이전트가 일하기 좋은 저장소인지 100점으로 재고 지도를 그린다 | 테스트 39개 |

"확인한 것"은 **돌려 본 것만** 적는다. 테스트 통과는 스크립트가 약속대로 움직인다는 뜻이고, 결과물이 언제나 맞다는 뜻은 아니다.

## 만드는 원칙

1. **정해진 동작은 코드로, 판단만 에이전트에게.** 세기·검사·배치는 스크립트, 무엇이 중요한지는 에이전트.
2. **관문이 있다.** 근거가 없으면 다음 단계로 가지 않는다.
3. **지우고 보내는 일은 매번 묻는다.** 기본은 꺼짐.
4. **짧게.** `SKILL.md`는 100줄 안쪽. 지워도 행동이 바뀌지 않는 문장은 지운다.

## 함께 쓰는 남의 스킬

직접 만들지 않았고 여기 복사해 두지도 않았다. 각 저장소의 안내를 따른다.

| 무엇 | 어디에 |
|---|---|
| 발표·대시보드 HTML | [visualize](https://github.com/careerhackeralex/visualize) (MIT) |
| HTML을 MP4로 | [hyperframes](https://github.com/heygen-com/hyperframes) (Apache-2.0) |
| 캐묻기·다시 쓰기 같은 일반 개발 스킬 | [mattpocock/skills](https://github.com/mattpocock/skills) (MIT) |

같은 사람이 만든 다른 저장소: [harness_framework](https://github.com/jha0313/harness_framework) · [second-brain-eval-kit](https://github.com/jha0313/second-brain-eval-kit) · [agentic-eng-plugin](https://github.com/jha0313/agentic-eng-plugin)

## 지원 종료

| 스킬 | 대신 |
|---|---|
| [presentation_slides](presentation_slides/SKILL.md) | [visualize](https://github.com/careerhackeralex/visualize) 또는 `into slides` |
| [ai-readiness-cartography-en](ai-readiness-cartography-en/README.md) | [ai-readiness-cartography](ai-readiness-cartography/README.md) `--lang en` |

설치한 사람의 경로가 깨지지 않게 폴더는 남기고 안내만 둔다. 자료: [claude-md-management 플러그인 설명](claude-md-management-plugin-explained.html)

## 설치 뒤

- 스킬은 폴더 전체가 있어야 한다(`SKILL.md`만 복사하지 않는다). 손으로 넣으려면 `~/.claude/skills/<이름>/`에 폴더째 복사한다. 이미 있으면 덮어쓰지 않게 먼저 확인한다.
- `skill-evaluator`·`eval-writer`는 Python 3.11+, `uv`, 인증된 Claude Code가 필요하다. `codex-review`는 로그인된 Codex CLI, `chief-of-staff`는 Git(PR까지 맡기면 로그인된 `gh`), `workflow-orchestrator`는 subagent를 띄울 수 있는 에이전트가 필요하다. `disk-cleanup-analyzer`는 macOS 전용이다. 나머지는 `python3`만 있으면 된다(`into`의 화면 검사는 Node와 puppeteer가 있으면 더 본다).
- 지우기: `npx skills remove <이름>`
