# into

에이전트 아웃풋을 **내가 이해하기 쉬운, 내가 정한 포맷**으로 바꾸는 스킬이다. 에이전트 답, PR, 디자인 문서, 논문·개념, 영상, X·스레드 글, 커뮤니티 글, 로컬 파일(프롬프트·코드·설정), 코드 저장소 전체나 하위 시스템을 매번 같은 칸(스캐폴드)에 채운다. 그리고 그 칸을 쉬운 말, STE 방식 문장, 문서, 한 장 HTML, 눌러 보는 HTML, 슬라이드, 테스트, 쇼츠, 영상으로 다시 만든다. 분야 하나를 조사해 전문가 과정으로도 만든다.

## 그냥 말로 시키면 되지 않나?

"쉽게 설명해줘"라고 말로 시켜도 답은 나온다. 하지만 매번 구조가 다르다. 어떤 날은 결론이 끝에 있고, 어떤 날은 다이어그램이 없다. into의 핵심은 **포맷**이다.

- 같은 칸이 같은 순서로 나오면 구조를 해석하지 않고 내용만 읽는다.
- 모드를 바꿔도 칸이 같아서 쉬운 설명 → 정확한 문장 → 그림 → 문서가 자연스럽게 이어진다.
- 칸은 사람마다 다를 수 있다. 내 칸으로 바꿔 쓸 수 있다(아래 "내 칸으로 바꾸기").

## 기본 칸

```text
1. TL;DR              무엇인가 · 핵심 동작 · 가장 중요한 숫자나 제약 하나
2. 왜 중요한가         푸는 문제 · 원문이 든 이유 · 영향받는 쪽
3. High-level design  구성 요소와 흐름 (사람·외부 시스템·앱·DB·큐)
4. Low-level design   핵심 경로 하나의 함수·데이터·호출 순서, 실패 경로
5. Insights           직관과 다른 점 · 흔한 오해 · 위험
빠진 디테일 · 출처
```

HLD는 "무엇과 무엇이 무엇을 주고받나", LLD는 "그 안에서 정확히 어떤 순서로 무엇이 불리나"다. 입력 유형마다 칸 이름과 순서는 같고 칸 안에 쓸 것만 조금 다르다. 예를 들어 PR의 Insights는 리뷰 포인트, X 글의 HLD는 주장과 근거의 구조다. 유형별 조정과 그 이유는 [references/scaffolds/](references/scaffolds/)에 있다.

## 모드

| 부르는 법 | 결과 | 위치 | 쓸모 |
|---|---|---|---|
| `into` | 기본 칸으로 답 | 대화 | 장황한 답을 바로 정리 |
| `into eli5`, 쉽게 설명해줘 | 쉬운 말 + 비유가 깨지는 곳 + 빠진 디테일 + 한 칸 위로 | 대화 | 처음 보는 주제의 입구 |
| `into ste`, STE 방식으로 | 짧고 모호하지 않은 문장, 숫자·한정어 보존 | 대화 | 디테일을 살린 정독, 남에게 넘길 글 |
| `into doc`, 문서로 만들어줘 | Mermaid 다이어그램이 든 이해 문서 | `into-out/<slug>-doc.md` | 공유, 다시 보기 |
| `into html`, visualize, 시각화해줘 | 한 화면 구조도 | `into-out/<slug>-html.html` | 큰 그림 한 장 |
| `into interactive`, 눌러 보는 HTML | 그림을 누르고 상황·갈림길을 골라 따라가기 | `into-out/<slug>-interactive.html` | 조건에 따라 길이 어떻게 바뀌는지 보기 |
| `into slides`, 슬라이드로 | 질문 사슬 + 발표자 노트 슬라이드 | `into-out/<slug>-slides.html` | 발표 |
| `into test`, 테스트 만들어줘 | 먼저 예측 → 답 → 피드백 퀴즈 | `into-out/<slug>-test.html` | 정말 이해했는지 확인 |
| `into shorts`, 쇼츠로 | 60초 세로 대본 + 스토리보드 (렌더 도구가 있으면 MP4) | `into-out/<slug>-shorts.md` | 쇼츠 업로드 |
| `into video`, 영상으로 | 긴 영상 대본 + 스토리보드 (렌더 도구가 있으면 MP4) | `into-out/<slug>-video.md` | 영상 업로드 |
| `into domain-expert <도메인>` | 조사 장부 → 비전·전략·목표·지표 → Easy·Medium·Hard·심화 섹션(결과물·채점표·게이트 퀴즈) 허브 | `into-out/<slug>-domain-expert/` | 한 분야의 전문가 과정 |

HTML 결과물은 외부 요청이 없는 단일 파일이다. 사용자가 경로를 주면 그곳에 쓴다.

## 사용 예

이어서 부르기:

```text
코덱스 하네스가 어떻게 동작하는지 설명해줘     ← 보통 질문. into를 쓰지 않는다.
into eli5      ← 쉬운 말. 끝에 '빠진 디테일'이 보인다.
into ste       ← 빠졌던 디테일을 살린 짧은 문장.
into html      ← 한 화면 구조도.
into doc       ← TL;DR · HLD · LLD · Insights 문서.
into shorts    ← 60초 대본과 스토리보드.
```

into는 매번 **같은 원본**에서 다시 만든다. 앞 결과를 다시 줄이지 않으므로 eli5에서 빠진 디테일이 ste·doc에서 돌아온다. 첫 into에서 칸마다 고른 사실을 다음 모드에서도 쓰므로 숫자·이름·다이어그램 노드가 모드 사이에서 일치한다.

그 밖의 예:

```text
into doc https://github.com/<owner>/<repo>/pull/123
이 논문 슬라이드로 만들어줘 https://arxiv.org/abs/<id>
into test ./prompts/system.md
into html ./my-repo                      ← 저장소 지도
into doc ./my-repo 구역: 샌드박스          ← 구역 하나 확대
이 스레드 쉽게 설명해줘 https://x.com/<user>/status/<id>
이 토론 시각화해줘 https://news.ycombinator.com/item?id=<id>
```

## 도메인 전문가 과정

`into domain-expert`는 원문 하나가 아니라 **분야 하나**를 받는다. 저장소면 코드를 지도와 구역으로 읽고, 업무·기술 분야면 논문·벤치마크, 대기업·중소기업·스타트업의 성공과 실패, 통계, 만드는 법, 사용자 언어권 자료를 조사해 등급(A~D)이 달린 장부를 만든다.

```text
into domain-expert ./my-repo
into domain-expert AI 에이전트 전환
into domain-expert 프롬프트 캐싱, 커리큘럼만
```

- 비전 하나 → 전략 하나 → 목표 하나 → 지표 3~6개. 섹션마다 비전·전략·목표·결과물·채점표·올리는 지표가 하나씩 있다.
- 레슨은 이 스킬의 다른 모드로 만든다. 처음 감은 eli5·shorts, 조건은 interactive, 근거는 doc, 긴 흐름은 video, 가르치기는 slides처럼 막히는 이유에 맞춰 고른다.
- 진단과 졸업 시험은 같은 설계, 다른 문제다. 퀴즈를 허브에서 풀면 점수와 지표가 저절로 찬다(브라우저에만 저장).
- 졸업 조건은 넷이다: 모든 섹션 통과(게이트 + 결과물), 졸업 시험, 졸업 과제, 직접 잰 지표(시작값과 지금 값). 졸업 과제에는 다른 사람이나 실제 사용으로만 채울 수 있는 필수 항목이 있다. 비전의 행동마다 남는 증거(`proof`)를 첫 화면에 보인다.
- 졸업 시험은 정답이 모두 낸 뒤에 보이고 첫 점수만 센다. 필수 증거가 모의면 졸업이 아니라 `연습 완료`다.
- 다 읽는다고 전문가가 되지는 않는다. 결과물과 졸업 과제를 통과해야 한다. 목표 값은 근거가 없으면 `(제안)`이라고 적힌다.

## 내 칸으로 바꾸기

- 한 번만: `into doc, 칸: 결론 / 근거 / 위험 / 다음 할 일`
- 계속: `references/scaffolds/<이름>.md`를 [general.md](references/scaffolds/general.md) 형식(섹션 순서, 섹션마다 쓸 것, 길이 한도, 다이어그램 규칙)으로 만들고 SKILL.md 1절의 판별 표에 한 줄을 더한다.

어떤 칸을 쓰든 출처 규칙은 같다: 원문에 없는 사실을 더하지 않고, 추론은 `(추정)`, 확인 못 한 것은 `(불확실)`로 표시하고, 줄인 것은 `빠진 디테일:`에 적는다.

## 설치

저장소 루트에서:

```bash
mkdir -p ~/.claude/skills
if [ -e "$HOME/.claude/skills/into" ] || [ -L "$HOME/.claude/skills/into" ]; then
  printf '기존 설치 보존: %s\n' into
else
  cp -R into "$HOME/.claude/skills/into"
fi
```

SKILL.md만 복사하지 말고 폴더 전체(references, assets 포함)를 설치한다. 다른 호스트는 그 호스트의 스킬 경로를 쓴다. 쇼츠·영상을 MP4로 렌더하려면 HTML→MP4 렌더 도구(예: `hyperframes` 스킬)가 따로 필요하다. 없으면 대본과 스토리보드까지만 만든다. 렌더할 때 한글 폰트는 프로젝트 안에 파일로 두고 임베드해야 깨지지 않는다.

## 알아 둘 것

- **STE 방식:** ASD-STE100은 ASD(유럽 항공우주·방위산업협회)가 관리하는 항공 정비 문서용 표준이다. NASA 표준이 아니다. 이 스킬은 표준의 승인 단어 사전과 대조하지 않으므로 결과를 "STE 준수"가 아니라 "STE 방식"이라고 부른다.
- **쉬운 설명의 위험:** 쉽게 바꾸면 사실이 틀어지거나 조건이 빠지기 쉽다. 그래서 eli5는 끝에 빠진 디테일과 "한 칸 위로"(실제 용어로 다시 올라간 설명)를 붙인다. 중요한 숫자는 원문으로 확인한다.
- **형식만 바꾸면 다시 읽기:** 바뀐 형식을 읽기만 하면 이해했다는 느낌만 남기 쉽다. `into test`로 먼저 예측해 보거나, eli5 뒤에 "내가 설명해 볼게"라고 하고 내 설명을 점검받는다.
- **읽을 수 없는 원문:** 로그인 벽이 있는 글, 자막이 없는 영상은 본문이나 자막을 붙여 넣어야 한다. 제목만으로 내용을 만들지 않는다.
- **쉬운 설명의 위험 2 — 짧은 한 줄:** 실행 평가에서 가장 많이 나온 문제는 틀린 사실이 아니라 제목·라벨·자막처럼 짧은 자리에서 조건과 한정어가 빠지는 것이었다. 규칙만으로는 줄지 않았다. 0.3부터는 쓰기 전에 사실마다 조건·한정어를 적은 "사실 카드"를 만들고, 쓴 뒤에 핵심어로 결과 전체를 검색해 모든 자리를 대조한다([references/fact-card.md](references/fact-card.md)).
- **저장소는 조건이 많다:** 코드에서는 설정 하나로 결과가 반대가 된다. codebase 스캐폴드는 경로 하나 옆에 분기 표를 두고, 구역마다 읽음·훑음·목록만을 적는다. `scripts/check_citations.py`가 근거의 파일·줄·이름을 저장소와 대조한다(조건·순서는 사람이 대조한다).
- **버전 0.7:** domain-expert 모드, domain 스캐폴드, 허브 템플릿과 빌드 스크립트를 더했다.
- **버전 0.6:** 큰 저장소 두 곳을 통째로 돌린 결과를 반영해 codebase 스캐폴드, interactive 모드, 근거·조건 대조 스크립트, 카드 반박 절차를 더했다. 0.4까지는 원문 50개 × 모드 8개 실행 평가를 반영했다.

## 폴더 구성

```text
into/
├── SKILL.md                  # 판별 → 칸 → 모드 → 출처 규칙 → 출력 위치
├── references/fact-card.md   # 사실 카드 · 짧은 자리 대조 · 금지 변형 예
├── references/scaffolds/     # general + 유형별 칸 9개
├── references/modes/         # eli5 · ste · doc · html · interactive · slides · test · shorts · video · domain-expert
├── scripts/                  # check_citations.py · check_facts.py (근거·조건 대조) · build_domain.py (과정 허브)
└── assets/                   # page.html · interactive.html · slides.html · test.html · domain-expert.html 템플릿
```
