# skills-lint

설치된 에이전트 스킬이나 스킬 저장소를 훑어 **규격 위반과 낡은 곳**을 보고합니다. 고치지는 않습니다.

## 언제

- 스킬이 안 불리거나 목록에서 사라졌을 때
- 스킬이 많아져 설명이 차지하는 양을 알고 싶을 때
- 스킬 저장소에 올리기 전, 그리고 CI에서

## 설치

```bash
npx skills add jha0313/skills_repo --skill skills-lint
```

필요한 것: Python 3.11+ (표준 라이브러리만). macOS에서 확인했습니다.

## 예시

> **나:** 스킬 점검해 줘. `deploy-notes`가 안 불려.
>
> **에이전트:** 스킬 12개, 오류 2, 경고 3. 먼저 고칠 것은 `deploy-notes`의 머리말입니다.
>
> | 스킬 | 문제 | 어디 | 왜 | 제안 |
> |---|---|---|---|---|
> | deploy-notes | 따옴표 없는 설명 안에 `: ` | `deploy-notes/SKILL.md:3` | 엄격한 YAML 파서가 못 읽어 목록에서 빠짐 | 설명을 `"…"`로 감싸기 |
> | api-review | 이름이 폴더(`api_review`)와 다름 | `api_review/SKILL.md:2` | 규격 위반, 설치 이름이 달라짐 | 폴더 이름 바꾸기 |
>
> 설명 합계 4,120자, 가장 긴 것은 `release-helper` 910자입니다. 어느 것을 고칠까요?

## 명령

```bash
python3 -I scripts/skills_lint.py                       # 설치된 스킬
python3 -I scripts/skills_lint.py --root .              # 저장소 하나
python3 -I scripts/skills_lint.py --root . --json --fail-on warning
```

- 설치된 스킬로 보는 폴더: `~/.claude/skills`, `~/.agents/skills`, `~/.codex/skills`, 지금 폴더의 `.claude/skills`, `.agents/skills`. 바로 아래 한 단계만 봅니다. 링크로 여러 번 설치한 스킬은 하나로 셉니다.
- `--root`는 다섯 단계 아래까지 찾습니다. `SKILL.md`가 있는 폴더 안, 링크 폴더, 숨긴 폴더(에이전트 폴더 제외), `tests`·`fixtures`·`evals`·`node_modules`는 건너뜁니다.
- 종료 코드: 0 문제 없음 · 1 `--fail-on` 수준 이상의 문제 있음 · 2 실행 못 함(폴더나 스킬이 없음).
- JSON 최상위: `schema`, `mode`, `skills`, `invocable`, `desc_chars_invocable`, `roots`, `longest`, `scripts_without_tests`, `trigger_overlaps`, `counts`, `issues`, `items`.

CI 예시:

```yaml
- uses: actions/checkout@v4
- run: python3 -I skills-lint/scripts/skills_lint.py --root . --fail-on error
```

이미 설치한 사람이 있어 바꿀 수 없는 옛 이름은 `--allow-name <이름>`으로 하나씩 예외로 둡니다. `name-format`만 건너뛰고 다른 검사는 그대로 합니다. 예: 이 저장소는 `--allow-name presentation_slides`가 필요합니다.

규격 검사(이름, 설명 1~1,024자, 필드 6개, compatibility 500자)는 [Agent Skills 규격](https://agentskills.io/specification)을 따릅니다(2026-11-24 확인). 에이전트마다 실제로는 더 느슨하게 읽기도 합니다.

## 못 하는 것

- **YAML 전체를 읽지 않습니다.** 흔히 깨지는 모양(따옴표 없는 `: `, 안 닫힌 따옴표, 특수 글자로 시작, 탭 들여쓰기, `키: 값`이 아닌 줄)만 봅니다. 따옴표로 감싼 키나 드문 문법은 거짓 경보가 날 수 있습니다.
- **플러그인으로 설치된 스킬은 기본으로 보지 않습니다.** 그 폴더를 `--root`로 주세요. 여러 버전이 함께 있으면 중복 이름으로 나옵니다.
- `trigger-overlap`은 설명에 **따옴표로 적은 말이 똑같을 때만** 찾습니다. 뜻이 비슷한 설명은 못 찾습니다.
- `stale-path`는 `SKILL.md`의 `scripts/`·`references/`·`assets/` 경로, 스킬 설치 경로, 홈 폴더 절대 경로만 봅니다. 다른 스킬에 같은 경로가 있으면 그것을 가리킨 것으로 보고 넘어갑니다. `~/.cache`처럼 실행 중에 생기는 경로는 보지 않습니다.
- 링크 검사는 `.md` 파일만 하고, 상대 링크는 그 문서가 있는 폴더에서 찾고, 제목 위치(`#절`)와 웹 주소는 확인하지 않습니다.
- 글자 수는 토큰 수가 아닙니다.

## 테스트

```bash
python3 -I tests/run_tests.py   # 임시 폴더의 가짜 스킬만 사용
```
