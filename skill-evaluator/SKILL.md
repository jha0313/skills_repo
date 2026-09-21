---
name: skill-evaluator
description: 격리 실행, 독립 채점, 재현 가능한 기준과 근거 보고서로 설치된 Claude Code 스킬을 평가·벤치마크·스트레스 테스트한다. 스킬 품질, 호출 정확성, 효율, 과제 완수, 회귀, 스킬 사용 유무 비교(evaluate, benchmark, stress-test, A/B)를 요청할 때 사용한다.
argument-hint: "[skill-name]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion Agent
metadata:
  version: "1.0.0"
  dependencies:
    discovery: "내장 scripts/discovery.py + 현재 claude plugin list --json"
    visualization: "내장 scripts/reporting.py"
    runtime: "Python >=3.11, uv, native plugin eval을 지원하는 Claude Code"
---

# 스킬 평가

지정한 설치 스킬을 처음부터 끝까지 평가한다. 격리 세션·실제 스킬 라우팅·MCP mock·원시 trace는 Claude Code의 **native `claude plugin eval`**을 재사용한다. 내장 조율 도구는 이식 가능한 기준, 독립 채점 라운드, 근거 검증, 재개, 발행 어댑터를 더한다. 먼저 `uv run <this-skill>/scripts/evaluate.py doctor`로 현재 help를 확인하고 그 계약을 따른다. Python 의존성은 uv가 고정된 script metadata에 따라 설치한다. CLI가 없으면 공식 [설치 안내](https://code.claude.com/docs/en/setup)를 따른다. CLI 자체가 없을 때 `claude install`을 실행할 수는 없다. 인증은 `claude auth login`, 기존 CLI 갱신은 `claude update`다. 내장 도우미가 없으면 새 디렉터리에 `git clone https://github.com/jha0313/skills_repo.git` 후 스킬 폴더 전체를 재설치한다. SKILL.md만 복사하지 않는다.

## 요청 해석

대상 이름·경로를 확인한다. 대상이 없거나 정말 모호할 때만 묻는다. 설치된 읽기 경로와 쓰기 가능한 소스를 구분한다(캐시 설치는 `--source`). `--basic`은 정확히 4개, 기본 THOROUGH는 10개, 깊이를 명시한 deep/comprehensive/thorough 요청은 `--deep` 30개다. `--binary`, `--local`, `--no-visualize`, `--judge-model`도 해석한다. 저장소가 승인한 고품질 모델 설정이 없으면 CLI 기본 모델을 따르고 실제 실행 모델을 기록한다. 임의로 승인된 모델이라고 설명하지 않는다. 추가 실행·발행 옵션은 `--help`를 확인한다.

## 순서대로 진행할 단계

1. **발견·분석.** 대상 소스 전체와 관련 references/assets/scripts/evals를 읽는다. 목적, 대상 사용자, 트리거·인자, 기능, 작업 흐름, 실제 사용 도구, 외부 시스템, 출력, 유형, 변경 동작과 근거, 경계 사례·실패 형태를 보존한다. 상위 plugin 의존성을 확인하고 미지원 항목은 조치 가능한 오류로 알린다. 읽기 전용은 병렬, 변경 동작은 native의 깨끗한 sandbox에서 순차 실행한다. 강한 환경 신호 3개 이상이면 자동 local을 선택한다. 1~2개는 가용 기능으로 안전하게 판단하고 해결되지 않을 때만 묻는다. 사용자 저장소를 reset/clean하지 않는다.
2. **기준 생성.** [test_case_format.md](references/test_case_format.md)를 읽는다. `prepare TARGET`이 분석과 기준을 생성하며 BASIC은 항상 표준 4개를 도출한다. THOROUGH는 서로 다른 10개 또는 30개 사례다. `--reuse-criteria`는 기존 대상 기준을 명시적으로 재사용한다. 덮어쓰기 전 타임스탬프 백업을 만든다. `--criteria FILE`로 받은 기준도 스키마·분포를 검증한다. 산출물 과제는 응답 주장뿐 아니라 실제 artifact 검사가 필요하다.
3. **검토·저장.** `CRITERIA_REVIEW.md`의 ID/범주/cwd/프롬프트/핵심 검사를 보여주고 수정할 기회를 준 뒤, 검토한 기준과 `--accept-criteria`로 실행한다. 사용자가 정확한 기준을 이미 승인했다면 다시 묻지 않는다. `prepare`는 검토 가능한 준비 단계이며 실행 완료를 뜻하지 않는다. 기준은 **대상 소스**의 `evals/eval_criteria.yaml`에 저장하고 `~/skill-eval/<name>/<run-id>/`에 사본과 해시를 보존한다. `--trust-target`은 대상/plugin이 이미 호스트의 승인된 신뢰 범위 안에 있다는 별도 확인이며 테스트 통과로 신뢰를 추론하지 않는다. 무관한 상태는 건드리지 않는다.
4. **실행.** [result_schema.md](references/result_schema.md)를 읽는다. local을 선택하지 않았고 검증된 MSL bridge가 있으면 우선 사용한다. 첫 사례의 실행 환경 오류는 native local로 전환할 수 있지만 실제 테스트 실패는 전환 사유가 아니다. invocation은 자연 라우팅으로 실행하고 스킬 지침을 강제 주입하지 않는다. 다른 사례는 스킬을 명시적으로 로드할 수 있다. 프롬프트, 전체 원시 trace, 출력만 담은 응답, 실제 호출, 사용량, 시간, 산출물·URL을 수집한다. `run --resume RUN_DIR`로 재개하며 불변 해시·옵션으로 revision 혼합을 막는다. 보존·봉인된 native sandbox는 데이터만 읽고 설정을 실행하지 않는다.
5. **채점.** [grading_rubric.md](references/grading_rubric.md) 또는 [grading_rubric_binary.md](references/grading_rubric_binary.md)를 읽는다. 기본 3개의 독립된 깨끗한 모델 세션이 **동일한** 실행 근거를 최대 4개 사례 단위로 채점한다. 1회·5회 변경은 명시적으로 기록한다. native `--runs 3`은 대상 에이전트를 반복 실행하는 옵션이며 독립 채점자 3명이 아니다. 모든 점수에는 해당 사례 출력·산출물의 정확한 인용문과 줄 검증이 필요하다. 프롬프트·스킬 지침은 수행 근거가 아니다. critical 실패를 평균으로 지우지 않는다. 읽을 수 없거나 빈 근거는 ERROR이며 점수를 지어내지 않는다. 시간 초과 전에 수행한 실질 작업은 timeout을 별도로 기록하고 채점할 수 있다. 바이너리 산출물은 도메인 렌더러로 확인한 뒤 채점한다.
6. **집계·보고.** [report_template.md](references/report_template.md)를 읽는다. `evaluations/`, `summary.json`, `REPORT.md`, 선택적 `REPORT.html`을 보존한다. 미확인 수치는 null이다. 업무 효과의 인과관계를 추론하지 않는다. SkillWatch/PixelCloud 발행에는 명시적 선택과 검증된 bridge 계약이 필요하며 기본은 로컬이다. 발행 상태를 미요청/미가용/mock/실제 실행으로 구분한다. 같은 실제 과제·모델·환경에서 스킬 사용 유무를 비교하고 채점 평균뿐 아니라 토큰과 실제 경과 시간을 비교한다. CLI `compare`는 기존 정규화 실행만 비교한다. 실제 무스킬 대조군은 [native ablation 절차](README.md)를 사용하고 별도 native 스키마를 보존한다.

## 명령

저장소 루트에서 실행한다. 아래는 안전한 인사말 fixture이지만 **실제 Claude 실행과 독립 채점**이므로 인증이 필요하고 모델 사용량이 발생한다.

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --basic --local --criteria skill-evaluator/tests/fixtures/basic.yaml --trust-target --no-visualize
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --local --criteria skill-evaluator/tests/fixtures/thorough.yaml --accept-criteria --trust-target
```

설치된 실제 스킬은 다음과 같이 평가한다. `<...>`는 실제 경로로 바꿀 자리표시자다.

```bash
uv run <this-skill>/scripts/evaluate.py prepare TARGET --local
uv run <this-skill>/scripts/evaluate.py run TARGET --criteria <target-source>/evals/eval_criteria.yaml --accept-criteria --trust-target --local
uv run <this-skill>/scripts/evaluate.py run --resume ~/skill-eval/TARGET/RUN-ID
```

호스트가 해당 실행을 승인한 범위에서 필요한 쓰기·셸 도구만 반복 가능한 `--allow-tool`로 허용한다. 스킬 평가가 외부 발행, 실제 MCP 접근, 소스 관리 변경까지 승인하는 것은 아니다. 발행 요청이 없으면 산출물은 로컬에 둔다. 새 기준과 채점 설명은 한국어로 작성하되 인용 근거·기계 필드·enum·명령·과거 실행 기록의 원문은 보존한다.
