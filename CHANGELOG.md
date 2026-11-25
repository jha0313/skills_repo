# 변경 기록

## 미정 — chief-of-staff 0.2

**바꿈**
- `chief-of-staff` — 비서실장은 관리만 한다. 승인받은 머지·게시·삭제·발송도 그 작업의 작업자가 brief의 `승인받은 행동`에 적힌 대상에만 한 번 실행한다(전에는 비서실장이 실행). herdr 안이면 작업자를 새 탭의 Claude 세션으로 띄우고, 보고판의 `작업 중`에 작업자가 있는 곳을 보인다. 턴을 끝내기 전 점검 세 줄. "너는 관리만 해", "워커 세션에서 해", "워커 세션 만들어서 맡겨"에도 켜진다. 이미 쓰던 `projects.md`의 안내 문장은 새 틀에 맞춰 바꾼다

## 미정 — into 2.0

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
