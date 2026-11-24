# ai-readiness-cartography

저장소가 코딩 에이전트와 일할 준비가 됐는지 100점으로 채점하고, 근거와 먼저 할 일을 한 장짜리 HTML로 보여 준다.

## 언제

- "이 레포 에이전트 친화적이야?", "AI 준비도 점수 매겨줘"
- CLAUDE.md·AGENTS.md에 적힌 경로가 실제로 있는지 확인하고 싶을 때
- 몇 달 뒤 다시 재서 전후를 비교하고 싶을 때

## 설치

```bash
npx skills add jha0313/skills_repo --skill ai-readiness-cartography
```

필요한 것: Python 3.11+. 다른 패키지는 없다. git이 있으면 낡음 판정이 정확하다.

## 예시

> **사용자:** 이 레포 AI 준비도 점수 매겨줘
>
> **에이전트:** 58/100 · AI-Fragile. 약한 곳은 C 숨은 지식(6/20)과 D 의존성 지도(4/15)입니다.
> 없는 경로 후보 3건을 열어 보니 2건은 옮겨진 파일, 1건은 빌드 때 생기는 파일이었습니다.
> 먼저 할 일: ① 틀린 경로 2건 고치기(약 30분) ② `docs/adr/`에 결정 이유 남기기(약 3시간) ③ 의존성 그림 추가(약 2.5시간). 시간은 추정입니다.
> 파일: `docs/ai-readiness-map.html`, `docs/ai-readiness-score.json`

스크립트만 써도 된다.

```bash
python3 -I scripts/score.py ~/work/acme-web                      # markdown 요약
python3 -I scripts/score.py ~/work/acme-web --json score.json    # JSON도 저장
python3 -I scripts/score.py ~/work/acme-web --lang en            # 문구만 영어, 점수는 같다
python3 -I scripts/fill_template.py score.json -o map.html       # 대시보드 복사본 채우기
python3 -I scripts/fill_template.py --check map.html             # 남은 자리 검사
python3 -I tests/run_tests.py
```

## 못 하는 것

- 파일과 낱말이 있는지만 본다. 문서가 맞는 말인지, 명령이 도는지는 사람이나 에이전트가 읽어야 한다.
- 점수가 높으면 에이전트가 더 잘한다는 뜻은 아니다. 반대 결과를 낸 연구도 있다(`references/scoring-rubric.md` "출처"). 배점과 등급은 이 스킬이 정한 것이다.
- 제목 판정은 영어 낱말만 본다. 한국어 제목만 쓰는 저장소는 C가 낮게 나온다.
- 폴더 없이 루트에만 코드를 둔 저장소, 깊은 워크스페이스(`crates/*` 등)는 module로 잘 나누지 못한다.
- "없는 경로"는 후보다. 만들어질 파일이나 다른 저장소의 파일이 섞인다.
- 저장소를 고치지 않는다. 읽기만 하고, JSON과 HTML 두 파일을 쓴다. 두 파일에는 저장소 이름·브랜치·파일 경로가 들어가니 공개하기 전에 확인한다.

## 바뀐 점 (2.1.0, 2026-11)

- `.tsx`를 `.ts`로 잘라 없는 경로로 세던 오류를 고침. `src/features|modules|domains/*`를 module로 인식. 둘 다 외부 기여 PR #1(@hahmee)에서 시작했다.
- 루트에 `AGENTS.md`만 있어도 감점하지 않음. 낡음은 git 커밋 시각으로 판정.
- 영어판을 합침(`--lang en`, `references/SKILL.en.md`). `ai-readiness-cartography-en`은 안내만 남는다.
- 템플릿을 자리표시로 바꾸고, 남은 자리를 검사하는 명령을 더함. JSON에 절대 경로를 남기지 않음.
- v2 점수와 비교할 수 없다(루브릭 v2.1).
