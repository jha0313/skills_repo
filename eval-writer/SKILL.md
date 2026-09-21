---
name: eval-writer
description: 설치된 에이전트 스킬의 재현 가능한 평가 기준을 작성·개선·검증한다. 스킬 평가나 변경 전에 eval 사례, 테스트 시나리오, 수준별 루브릭, 부정 라우팅, 도구 mock fixture를 작성할 때 사용한다. 검토한 기준과 실행 인계를 만들며 스키마 유효성을 실제 스킬 평가 통과로 해석하지 않는다.
argument-hint: "[skill-name] [--basic|--deep] [--binary]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion
metadata:
  version: "1.0.0"
  dependencies:
    evaluation-framework: "skill-evaluator/scripts/evaluate.py 및 references/test_case_format.md"
    runtime: "uv, Python >=3.11, native plugin eval을 지원하는 인증된 Claude Code"
---

# 평가 기준 작성

대상 스킬의 실제 계약을 서로 다르고 재현 가능한 평가 사례로 바꾼다. **skill-evaluator의 `prepare`·`validate` 명령**, 스키마, 백업, 소스 발견 기능을 재사용한다. 별도 runner·judge·점수 공식·발행기를 만들지 않는다. 이 스킬은 기준 작성용이며 대상 실행에는 실행 요청 또는 기존 평가 승인이 필요하다.

## 대상과 의존성 확인

1. 설치된 스킬 이름이나 SKILL.md의 정확한 디렉터리를 확정한다. 없거나 정말 모호할 때만 묻는다. 해당 저장소 지침, 대상 진입 문서 전체, 관련 references/scripts/assets/기존 evals를 읽는다.
2. 같은 묶음의 형제 경로나 실제 설치 skill/plugin root에서 `skill-evaluator/scripts/evaluate.py`를 찾는다. 파일 시스템으로 확인하고 절대 홈 경로나 plugin namespace를 지어내지 않는다. evaluator의 **현재** `references/test_case_format.md`와 CLI `--help`를 읽는다.
3. 의존성이 없으면 새 디렉터리에 `git clone https://github.com/jha0313/skills_repo.git` 후 eval-writer·skill-evaluator 전체 폴더를 함께 설치하도록 안내하고 멈춘다. 기존 설치를 덮어쓰지 않는다. CLI 의존성 확인이 실패하면 그 설치·갱신 오류 안내를 따른다.
4. 설치된 읽기 경로와 쓰기 가능한 소스(`--source`)를 구분한다. 다른 스킬의 기준을 eval-writer/evaluator 디렉터리에 저장하지 않는다. 평가 대상 자체가 이 둘 중 하나인 것은 가능하다.

## 작성 옵션 확정

- 기본 THOROUGH는 10개. `--basic`은 표준 범주 4개. `--deep`/`--comprehensive` 또는 명시적인 확장 deep/thorough/comprehensive 요청은 30개다.
- `--binary`는 관찰 기준을 갖춘 0/1과 PASS/FAIL. 그 외에는 evaluator의 Likert 1~5다. 세미나의 별도 팀 점수 규칙(critical 실패→0, 품질 .5~1)은 **이 스키마가 아니다**.
- 주어진 `--source`, `--judge-model`, `--judge-timeout`, `--output`을 전달한다. 작성자는 evaluator의 독립 작성 모델을 사용한다. 승인된 저장소 모델이 없으면 있다고 주장하지 않는다.
- 기본은 새 기준. `--reuse-criteria`는 명시적으로 요청했을 때만 쓴다. 상대 CLI 경로는 기록한 working directory를 기준으로 해석한다.

## 작성 순서

### 1. 계약과 검사 대응표

의미 있는 규칙마다 소스 경로·절, 관찰할 동작, 가능한 실패, 둘을 구분할 근거를 찾는다. 트리거·인자 처리, MUST/NEVER 규칙, 산출물, 도구 요구, 의존성 오류를 포함한다. 실제 변경 동작을 분류한다. Bash 권한만으로 변경한다고 판단하지 않는다.

[authoring-guide.md](references/authoring-guide.md)의 품질 점검과 지식·호출 구분을 읽는다. '지침을 따른다'를 반복하지 말고 실제로 다른 계약에 연결된 사례를 만든다.

### 2. 기존 프레임워크로 준비

확인한 evaluator 경로를 쓴다. 기준 생성·동작 분석을 수행하고 기존 대상 기준을 교체하기 전에 타임스탬프 백업을 만들며 manifest와 검토 표를 남긴다. 대상을 실행하거나 채점하지는 **않는다**.

```text
uv run <evaluator>/scripts/evaluate.py prepare <target-read-path> --local [--source <target-source-path>] [--basic|--deep] [--binary]
```

꺾쇠 값과 대괄호 옵션은 표기법이며 그대로 셸에 붙여 넣지 않는다. 기본 THOROUGH는 크기 flag를 생략한다. 생성된 analysis.json, 대상 evals/eval_criteria.yaml, CRITERIA_REVIEW.md를 확인한 뒤 작성 완료를 보고한다.

### 3. 검토와 수정

범주 배분, 구별되는 동작, 근거 있는 루브릭, 필수 산출물, 명시적 timeout, mock 범위를 소스와 대조한다. **추가로 기준을 덮어쓸 때마다** evaluator의 `core.backup_write`를 쓴다. prepare가 이미 백업했다는 이유로 생략하지 않는다. 대상 소스에 revision을 남기고 작성 보고에 백업 경로를 포함한다.

Invocation 프롬프트는 실제 자연 라우팅을 검사한다. 사례 수에 맞게 긍정·부정·모호성·인자 추론을 포함하고 슬래시 호출, 주입한 스킬 지침, 강제 맥락을 쓰지 않는다. 다른 지식 검사는 스킬 이름과 '어떤 규칙을 따라야 하나요?' 같은 질문을 쓴다. 실제 완수 검사는 실제 산출물을 요청한다. 지식 답변으로 산출물 완성을 입증할 수 없다.

계약상 필요할 때만 정확한 문구를 강제한다. 사례별 관찰 기준을 갖춘 의미 질문을 우선한다. 필수 조건은 `critical: true`; 표시하지 않은 의미 검사는 이 evaluator에서 진단용이다. Likert 모음은 **critical도 1~5의 다섯 수준이 모두 필요하다**. Critical 실패는 3 미만이며 별도 0/1 루브릭이 아니다. Likert 기준에 Binary critical을 섞지 않는다. 통과시키려고 실패 기준을 약화하지 않는다.

호출 가로채기에는 mock 데이터가 필요하다. 실제 도구 목록으로 정확한 MCP runtime 이름·input schema를 확인하고 설정 alias로 추측하지 않는다. 목록을 얻을 수 없으면 미해결 의존성과 필요한 근거를 보고하며 지어낸 이름을 검증 완료로 표시하지 않는다. 알 수 없는 실제 호출은 차단하거나 runner 미지원으로 명시한다. 외부 응답을 mock해도 모델 출력이 결정적으로 바뀌지는 않는다.

새 사례 이름·프롬프트·예상 동작·루브릭은 한국어로 작성한다. 영문 트리거 자체를 검증하는 사례만 영문을 쓰고 목적을 표시한다. 기술 식별자·기계 필드·정확한 계약 문구·과거 근거는 원문을 유지한다.

### 4. 형식 검증과 인계

```text
uv run <evaluator>/scripts/evaluate.py validate <target-source>/evals/eval_criteria.yaml [--basic|--deep] [--binary]
```

작성 때와 같은 모드·척도를 쓴다. 스키마 검증은 필요하지만 의미 품질 검토나 대상 동작 입증은 아니다. ID/범주/cwd/정확한 프롬프트/핵심 기준의 짧은 표를 보여주고 수정할 기회를 준다. 기존 승인에 검토 후 실행이 포함되면 진행한다. 아니라면 준비된 산출물과 정확한 실행 명령을 전달하되 eval 통과를 주장하지 않는다.

준비한 실행은 불변으로 보존한다. 기준을 편집했다면 `--criteria <edited-file> --accept-criteria`로 **새** 평가를 만든다. 기존 manifest를 수정하거나 오래된 기준을 재개하지 않는다. 준비된 기준 그대로 재사용하려면 그 정확한 기준을 검토해야 한다.

YAML/JSONL 교환에서 정식 실행 파일은 evaluator YAML이며 JSON도 유효한 YAML이다. JSONL 요청 시 사례 하나를 완전한 한 줄로 내보내고 상속한 working_directory를 구체화하며 기본값·모드·source hash를 sidecar에 보존한다. 정식 YAML을 다시 검증하고 YAML CLI에 원시 JSONL을 넣지 않는다. 형식 내보내기일 뿐 두 번째 평가 형식·엔진이 아니다.

## 최종 작성 보고

기준, 분석·검토 표, 타임스탬프 백업, 선택적 JSONL/sidecar 경로를 반환하고 모드·척도·사례 배분을 밝힌다. 서로 다른 계약, 빈틈, mock 출처, 수행한 검증을 요약한다. 작성만 했다면 **대상 평가는 실행하지 않음**을 명시한다.

현재 CLI help와 선택 대상·모드에 맞는 다음 run 명령을 준다. 대상 신뢰가 사용자 승인 범위 안에 있을 때만 --trust-target을 포함하고 필요한 도구만 허용한다. Eval-driven 흐름을 설명한다: 새 사례의 의도한 실패 확인 → 스킬 수정 → 같은 기준으로 재평가 → 회귀 확인 → 반영. 환경 고장으로 난 실패는 의도한 red 단계가 아니다.

개선 주장은 같은 과제·모델·시작 상태·완수 임계값·mock 환경의 스킬 사용 유무 비교와 토큰·실제 경과 시간 측정이 필요하다. 독립 채점 반복은 변동을 줄이지만 공통 편향을 없애지 않는다. 작성 기준에 지어낸 점수·업무 개선을 넣지 않는다.
