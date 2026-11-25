# _common — 모든 유형이 함께 쓰는 약속

- 자리: one(한 줄) → why(왜) → pic(그림 하나) → run(실제로 도는 순서·근거) → catch(조심할 것·뜻밖). 이름과 모양은 유형마다 다르고 순서는 같다.
- 한도는 최대치다. 채울 것이 없으면 비운다. 그림·표 칸을 비우면 model에서 채우고 `false`면 뺀다.
- 한도 뒤의 표시: `!` 필수 · `?` 없어도 되는 칸(`빈 칸`으로 적지 않는다) · `~` 근거 없이 써도 되는 칸(비유·질문).

## 길이

| 모드 | 작음 | 보통 | 큼 |
|---|---|---|---|
| brief | 500 | 800 | 1000 |
| eli5 | 480 | 730 | 930 |
| ste | 700 | 1100 | 1500 |
| html | 480 | 730 | 930 |
| interactive | 1200 | 1800 | 2500 |
| doc | 1500 | 3000 | 6000 |

## 형

| 형 | 값 | 글 모드에서 |
|---|---|---|
| line | 문장 하나 | 한 줄 |
| list | 문장 여러 개 | 짧으면 `· ` 한 줄, 길면 글머리 |
| steps | 순서 있는 단계 | 번호 |
| beforeafter | 모델 간선 id(when이 before·after) | 전 / 후 두 줄 |
| flow | 모델 간선 id | 화살표 줄 |
| map | 모델 zones | `구역 — 하는 일` 줄 |
| lanes | 모델 steps(lane) | 코드 블록. 한 단계 한 줄 `레인  하는 일 ─(넘기는 것)▶ 다음 레인` |
| timeline | 모델 chapters | `mm:ss 장면` 줄 |
| ladder | 모델 claims | 모델 순서의 줄. 근거 종류는 이름표 |
| positions | 모델 positions | `입장(n) — 한 줄` |
| options | 모델 options·criteria | 표 |
| anatomy | 모델 parts | `줄 범위 — 하는 일` |
| chart | 모델 results | 표(글), 막대(html) |
| table:열,열 | 행 배열 | 표 |
| qa | 질문과 답 | `Q. → A.` |
| quote | 원문 그대로 | 따옴표 |
| number | 값·단위·무엇의 | 굵게 |
| code | 파일·줄 범위 | 원문 줄 인용 |
| kit:<부품> | 부품 데이터 | (html·interactive에서만) |

## brief

| 자리 | 칸 | 키 | 형 | 한도 | 쓸 것 |
|---|---|---|---|---|---|
| one | TL;DR | one | line | 90! | 무엇인가 + 핵심 동작. 형용사보다 동사 |
| why | 왜 중요한가 | why | list | 2×70 | 어떤 문제를 푸나. 원문이 든 이유 |
| pic | High-level design | pic | flow | 6 | 누가 무엇을 주고받나. 함수·필드 이름 금지 |
| run | Low-level design | run | steps | 5×70 | 그림의 화살표 하나를 확대. 실제 식별자와 순서 |
| catch | Insights | catch | list | 3×70 | 직관과 다른 점, 뒤집는 조건, 조용한 실패 |
