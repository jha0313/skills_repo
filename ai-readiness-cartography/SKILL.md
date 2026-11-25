---
name: ai-readiness-cartography
description: 저장소가 코딩 에이전트와 일할 준비가 됐는지 100점(7개 카테고리)으로 채점하고, 근거 JSON·한 장짜리 HTML 대시보드·먼저 할 일 목록을 만든다. "AI 준비도 점수 매겨줘", "AI-readiness 지도", "이 레포 에이전트 친화적이야?", "CLAUDE.md·AGENTS.md 점검", "audit our codebase for agent readiness", "repo cartography"에 쓴다. 코드 리뷰나 보안 점검에는 쓰지 않는다.
license: MIT
compatibility: Python 3.11+ (표준 라이브러리만). git이 있으면 낡음 판정이 정확하다. 대시보드는 Google Fonts를 부르며, 오프라인이면 시스템 글꼴로 보인다.
metadata:
  version: "2.1.0"
---

# AI-Readiness Cartography

이 SKILL.md가 있는 폴더를 `SKILL_DIR`, 채점할 저장소를 `REPO`라 한다. English: `references/SKILL.en.md`.

**한계 먼저.** 채점은 파일이 있는지, 낱말이 있는지를 보는 어림이다. 점수가 높으면 에이전트 성공률이 오른다는 증거는 아니다(근거와 반대 연구: `references/scoring-rubric.md` "출처").

## 1. 언제 쓰나

- 저장소에 CLAUDE.md·AGENTS.md·README가 얼마나 있고 맞는지 한눈에 보고 싶을 때, 무엇부터 고칠지 정할 때.
- 쓰지 않는 때: 버그·보안 리뷰, 사람 개발자용 문서 평가, 두 저장소의 순위 매기기(구조가 다르면 점수를 비교할 수 없다).

## 2. 순서

**1) 채점.** `python3 -I SKILL_DIR/scripts/score.py REPO --json OUT/ai-readiness-score.json` (영어 보고면 `--lang en`)
- `OUT`: 사용자가 준 경로 > `REPO/docs/` > `REPO/.claude/` > `REPO`. 이미 같은 이름의 파일이 있으면 덮어쓰기 전에 묻는다.
- 완료: 종료 코드 0, JSON에 `total`과 A~G 7개가 있다. JSON이 없으면 다음 단계로 가지 않는다.

**2) 후보 확인.** `categories.E.evidence.broken_refs`를 하나씩 연다. 정말 없는 경로 / 만들어질 파일·다른 저장소·예시라서 괜찮은 것으로 나눈다.
- `F.evidence.time_basis`가 `git`이 아니면(`mtime`, `git+mtime`, `shallow`, `none`) 보고에 그 이유를 적는다.
- 완료: 후보마다 판정이 하나씩 있다. 판정하지 않은 후보를 "틀린 경로"라고 쓰지 않는다.

**3) 대시보드 채우기.** `python3 -I SKILL_DIR/scripts/fill_template.py OUT/ai-readiness-score.json -o OUT/ai-readiness-map.html`
- 숫자·색·막대·라벨·할 일 목록은 스크립트가 채운다. 남은 자리 10개만 만든 HTML에 글로 쓴다(아래 표).
- 완료: `python3 -I SKILL_DIR/scripts/fill_template.py --check OUT/ai-readiness-map.html`이 "통과". 남은 `{{자리}}`가 있으면 열거나 보고하지 않는다.

**4) 눈으로 확인하고 열기.** 글자 겹침·잘림이 없는지 본다. `open`(macOS) / `xdg-open`(Linux). 열지 말라고 하면 경로만 알린다.

| 자리 | 누가 | 넣을 것 |
|---|---|---|
| `{{REPO_NAME}}` `{{SCORED_AT}}` `{{GIT_BRANCH}}` `{{MODULES_TOTAL}}` `{{CONTEXT_FILES_TOTAL}}` `{{RUBRIC_VERSION}}` `{{LANG}}` | 스크립트 | `meta` |
| `{{TOTAL_SCORE}}` `{{GRADE}}` `{{GRADE_COLOR}}` `{{COVERED_MODULES}}` `{{BROKEN_REFS}}` `{{LARGE_FILES}}` | 스크립트 | 총점·등급·요약 숫자 |
| `{{X_SCORE}}` `{{X_PCT}}` `{{X_BAR}}` (X = A~G) `{{B_SUBS}}` `{{E_SUBS}}` | 스크립트 | 카테고리 점수·막대 |
| `{{ACTION_ITEMS}}` | 스크립트 | `actions` 앞 7개 |
| `{{T_*}}` | 스크립트 | 화면 라벨(ko·en) |
| `{{SCORE_DESC}}` | 나 | 가장 약한 2개 카테고리와 이유, 한두 문장 |
| `{{X_NOTE}}` (X = A~G) | 나 | 근거 1~2개. 숫자는 JSON에 있는 값만 |
| `{{MAP_SVG}}` | 나 | 구조 지도. `references/map-snippets.md`의 조각을 복사해 쓴다 |
| `{{WINS_ITEMS}}` | 나 | 점수가 높은 카테고리의 근거 3~5개, `<li>` 조각 |

## 3. 근거로 보여 줄 것

- 실행한 명령과 총점 줄, E1 후보의 판정, `--check` 통과 줄.
- 등급: 90↑ AI-Native · 75↑ AI-Ready · 60↑ AI-Assisted · 40↑ AI-Fragile · 그 아래 AI-Hostile.
- 스크립트가 못 보는 것(명령·핵심 파일·숨은 규칙의 깊이, 리뷰와 프롬프트 시험의 질)은 직접 읽고 글로만 덧붙인다.

## 4. 하지 말 것

- **점수를 손으로 바꾸지 않는다.** 같은 저장소가 같은 점수를 받아야 다음 측정과 비교할 수 있다.
- **`assets/template.html` 원본에 값을 쓰지 않는다.** 한 저장소의 이름과 점수가 스킬에 남아 다음 사람에게 새어 나간다.
- **재지 않은 절감 수치를 만들지 않는다**("토큰 30% 절감" 등). 시간과 우선순위는 스크립트의 추정값이라고 밝힌다.
- **결과를 공개하기 전에 묻는다.** HTML·JSON에는 저장소 이름, 브랜치, 파일 경로가 들어간다.
- **디자인을 새로 만들지 않는다.** 글꼴·색·배경은 템플릿 그대로, 차트 라이브러리·이모지·지도 장식은 넣지 않는다. 매번 달라지면 전후 비교가 안 된다.
- **점수를 올리려고 빈 CLAUDE.md를 만들지 않는다.** 고치는 일은 이 스킬의 범위가 아니다. 사용자가 시킬 때만 한다.

## 답 형식

1. 총점과 등급 한 줄 (`NN/100 · 등급`).
2. 가장 약한 카테고리 1~2개와 이유.
3. 먼저 할 일 3개(추정 시간 포함).
4. E1 후보 판정 결과와 낡음 판정 기준(`time_basis`).
5. 만든 파일의 경로.

채점 기준을 물으면 `references/scoring-rubric.md`를 읽는다.
