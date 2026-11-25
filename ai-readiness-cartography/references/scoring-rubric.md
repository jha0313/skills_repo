# AI 준비도 루브릭 v2.1 (100점 · 7 카테고리)

이 문서는 `scripts/score.py`가 **실제로 계산하는 것**을 적는다. 사람이 볼 것은 "사람 확인"에 따로 적고, 점수에는 넣지 않는다.

| 카테고리 | 이름 | 점수 |
|---|---|---|
| A | AI Navigation & Coverage — 어디를 봐야 하는지 찾을 수 있나 | 15 |
| B | Context Document Quality — 안내 문서가 짧고 쓸모 있나 | 20 |
| C | Tribal Knowledge Externalization — 숨은 규칙이 글로 있나 | 20 |
| D | Cross-Module Dependency Mapping — 바꾸면 어디가 흔들리는지 아나 | 15 |
| E | Verification & Quality Gates — 안내와 변경을 검증하나 | 15 |
| F | Freshness & Self-Maintenance — 안내가 낡지 않나 | 10 |
| G | Agent Performance Outcomes — 효과를 재나 | 5 |

**용어.** context 파일 = `CLAUDE.md`, `AGENTS.md`, `README.md`(링크로 이어진 같은 파일은 한 번만 센다). 핵심 module = 코드가 든 루트 폴더, `apps/*`·`packages/*`·`services/*`의 각 폴더, 그리고 `src/features|modules|domains/*`(코드가 든 하위 폴더가 2개 이상일 때. `src`는 그 밖의 코드가 남을 때만 module로 센다. 도메인에 자기 파일이 없으면 `src/features` 등이나 `src`의 안내를 물려받는다).

## A. 탐색 · 15

`round(context 있는 module ÷ 전체 module × 15)`. 루트에 `CLAUDE.md`도 `AGENTS.md`도 없으면 2점을 뺀다(둘 중 하나면 된다). 루트에 바로 둔 코드는 module로 세지 않아, 폴더가 없는 작은 저장소는 A와 C가 0점이다.

## B. 문서 품질 · 20 (항목마다 4점, 모든 context 파일의 평균)

| 항목 | 통과 조건 |
|---|---|
| B1 Conciseness | 10~80줄 |
| B2 Quick Commands | bash·sh·zsh·console 코드 블록이 있다 |
| B3 Key Files | 파일 경로 3개 이상(1~2개면 절반) |
| B4 Non-Obvious | `Why:` `Note:` `Gotcha` `Warning` `Don't` `Caveat` `Important:` `반드시` `주의` 중 하나 |
| B5 Cross References | 상대 링크가 있다 |

**사람 확인:** 명령이 실제로 도는지, 적힌 파일이 정말 핵심인지, 규칙이 실패를 막아 주는지.

## C. 숨은 지식 · 20 (다섯 질문, 4점씩)

1. 무엇을 맡나 — 제목에 purpose·owns·configures·overview, 또는 본문에 owns·configures
2. 흔한 수정 방법은 — 제목에 pattern·how to·common change·workflow·recipe
3. 실패를 부르는 숨은 규칙은 — B4와 같은 표시
4. 다른 module과의 의존은 — 제목에 depend·cross-module·import·see also·related, 또는 본문에 depends on
5. 결정 이유를 남기는 곳은 — `MEMORY.md`, `docs/adr`, `docs/decisions`, `adr`, `.claude/memory*`

1~4는 module 평균, 5는 저장소에 하나. 제목 판정은 **영어 낱말**만 본다. 한국어 제목만 쓰는 저장소는 실제보다 낮게 나온다.

## D. 의존성 지도 · 15

`ARCHITECTURE.md`·`docs/architecture.md`·`docs/dependency-graph.md`·`docs/data-flow.md` 중 하나 6점 · context 파일의 mermaid 3점 · 의존성 절이 context 파일 절반 이상 4점(하나라도 있으면 2점) · `turbo.json`·`nx.json`·`pnpm-workspace.yaml`·`lerna.json` 2점.

## E. 검증 · 15

| 항목 | 점수 | 계산 |
|---|---|---|
| E1 Reference Accuracy | 5 | context 파일의 경로 중 실제로 있는 비율 × 5. 경로가 없으면 2 |
| E2 Critic Review | 4 | CODEOWNERS 2 + PR 템플릿 2 |
| E3 Task Validation | 4 | `package.json`·`pyproject.toml`·`Makefile` 중 하나 2 + husky 1 + GitHub 워크플로 1 |
| E4 Prompt Tests | 2 | `evals`·`benchmarks`·`agent-evals`·`prompts/test`·`tests/agent` 폴더 |

**E1 규칙.** 폴더가 하나 이상 든 경로(`src/app/page.tsx`)만 본다. URL, `~/`·`$HOME/`·`<자리>/`로 시작하는 것은 뺀다. 문서가 있는 폴더부터 저장소 루트까지 올라가며 기준으로 삼아 하나라도 있으면 통과다. 남은 것은 **후보**다. 만들어질 파일, 다른 저장소의 파일, 예시일 수 있으니 열어서 판정한다.

**사람 확인:** 리뷰와 프롬프트 시험의 질, 검증 명령이 실제로 도는지. E3는 `Cargo.toml`·`go.mod` 같은 다른 빌드 파일을 보지 않는다.

## F. 최신 상태 · 10

- 낡음 6점: `6 × (1 − 낡은 module 비율)`. module의 context 파일보다 코드의 마지막 커밋이 **30일 넘게 새로우면** 낡음.
- 시각은 git 커밋 시각이다. clone하면 파일 시각이 모두 같아져 쓸 수 없기 때문이다. 커밋 안 된 module은 파일 시각(mtime)으로 보고 `time_basis`에 표시한다. 얕은 clone은 판정하지 않고 중간 점수 3점을 준다.

| `time_basis` | 뜻 |
|---|---|
| `git` | 모두 커밋 시각 |
| `git+mtime` | 일부는 커밋이 없어 파일 시각 |
| `mtime` | git 기록 없음. 복사·압축 해제 뒤에는 믿을 수 없다 |
| `shallow` | 얕은 clone. 판정 안 함 |
| `none` | 잴 module이 없음 |

- CI 2점: 워크플로 파일에 `context`·`docs`·`claude`·`adr`·`reference` 낱말이 있다. 실제로 검사하는지는 보지 않는다.
- hook 2점: `.husky/pre-commit` 또는 `pre-push` 파일이 있다. 내용은 보지 않는다.

## G. 성과 측정 · 5

`evals`·`benchmarks`·`agent-evals`·`agent-metrics` 폴더 3점 · `agent-results.json`·`.skill-eval.json` 1점 · 루트 문서에 telemetry 관련 낱말 1점. 재 볼 만한 것: 작업 통과율, 작업당 도구 호출과 토큰, 다시 한 PR 비율.

## 등급

| 점수 | 등급 | 색 |
|---|---|---|
| 90~100 | AI-Native | green |
| 75~89 | AI-Ready | green |
| 60~74 | AI-Assisted | amber |
| 40~59 | AI-Fragile | amber |
| 0~39 | AI-Hostile | red |

등급 경계와 배점은 이 스킬이 정한 것이다. 외부 표준이 아니다.

## 할 일 순서

`우선순위 = 영향(1~10) ÷ 시간`. 영향과 시간은 스크립트에 적어 둔 **추정값**이고 잰 값이 아니다. 시간 표시: S = 1시간 이하, M = 4시간 이하, L = 그 이상.

## v2 → v2.1 (점수가 달라지는 곳)

- 경로 추출: `.tsx`·`.jsx`·`.json`을 자르던 오류, URL·점 폴더·하이픈 폴더를 잘못 세던 오류를 고침 → E1이 오를 수 있다.
- 루트 `AGENTS.md`만 있어도 A에서 감점하지 않음.
- 낡음을 git 커밋 시각으로 판정 → F가 바뀔 수 있다.
- `src/features|modules|domains/*`를 module로 셈 → 도메인마다 문서가 있으면 A·C·F가 오른다. `src`에 안내 하나만 있어도 물려받으므로 깎이지 않는다.

v2 점수와 v2.1 점수는 비교하지 않는다.

## 출처 (2026-11-24 확인)

- Meta 엔지니어링 글 [How Meta Used AI to Map Tribal Knowledge in Large-Scale Data Pipelines](https://engineering.fb.com/2026/04/06/developer-tools/how-meta-used-ai-to-map-tribal-knowledge-in-large-scale-data-pipelines/) (2026-04-06): 다섯 질문, "compass, not encyclopedia"(25~35줄, 약 1,000토큰), 참조 경로를 모두 검증해 환각 0건, 몇 주마다 자동 점검. 한 회사의 사례이고, 효율 결과는 작업 6개의 예비 시험이라고 밝힌다. 이 루브릭은 그 생각을 참고했다.
- 반대 근거: [Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/abs/2602.11988) (2026-02-12, v3 2026-09-29). context 파일이 대체로 작업 성공률을 높이지 않았고 추론 비용은 평균 20% 넘게 늘었다. 저장소 개요는 도움이 안 됐고, 일반적이지 않은 규칙을 적는 데는 쓸모가 있다고 본다. **그래서 파일 수를 늘리는 것보다 틀린 경로를 고치고 숨은 규칙을 적는 일을 앞에 둔다.**
