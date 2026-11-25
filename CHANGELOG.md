# 변경 기록

## 미정 — into 2.0

**더함**
- `into` — 결과 모양 셋: 퀴즈, 쇼츠·롱폼 대본(`into/outputs/`). 말했을 때만 쓰고, 자료 포맷은 하나 고르는 그대로다. 렌더러나 스크립트는 없다

**바꿈**
- `into` — 뼈대(포맷)만 남겼다. 렌더러·검사 스크립트·모드(eli5, ste, html, interactive, doc, slides, 퀴즈, 쇼츠, 영상)를 뺐다. 말투는 사용자가, 그리기는 visualize 같은 스킬이 맡는다. 개념·커리큘럼 포맷을 더하고 단계를 셋으로(간단히·자세히·아주 자세히). 옛 판은 커밋 `71e7baa`

## 2026-11-24 — 저장소 다시 디자인

**더함**
- `chief-of-staff` 0.1, `codex-review`, `skills-lint`, `disk-cleanup-analyzer`, `time-convert` 공개판
- MIT 라이선스, Claude Code 마켓플레이스(`silbal`), skills.sh 묶음, 기여 안내, 저장소 검사(`scripts/check_repo.py`)와 CI

**바꿈**
- `into` 1.0 — 원문을 한 번 읽어 모든 모드가 함께 쓰고, 세기·검사·배치는 스크립트가 한다. 유형 열 가지마다 시험해 고른 틀(`formats/`). 결정과 이유, 잰 값과 못 하는 것은 그 판의 DESIGN.md(커밋 `71e7baa`)
- `ai-readiness-cartography` — 확장자 잘림과 없는 경로 오탐을 고치고(외부 기여 PR #1, hahmee), 낡음 판정을 git 커밋 시각으로, 한·영을 한 벌로(`--lang`). 템플릿에 남아 있던 예시 값을 자리표시로 바꿨다. v2와 v2.1 점수는 비교할 수 없다.
- `improve-token-efficiency` — 가격을 한 파일로 모으고 공식 가격표로 다시 확인, 중복 기록 제거, 폴더 찾기 수정, 근거 없는 조언 제거
- `skill-evaluator` — CI에서 실제 Claude CLI를 요구하던 테스트 수정

**지원 종료**
- `presentation_slides` → visualize 또는 `into slides`
- `ai-readiness-cartography-en` → `ai-readiness-cartography --lang en`

## 2026-11-24 — into 0.7
- 저장소 스캐폴드, interactive, 전문가 과정(domain-expert)

## 2026-11-20 — into 0.4
- 같은 다섯 칸 스캐폴드와 8개 모드
