# 이식 가능한 평가 기준·생성·모킹

정식 기준 파일은 `TARGET/evals/eval_criteria.yaml`이다. JSON은 YAML 1.2의 유효한 문서이며 도우미는 정확한 프롬프트를 보존하기 위해 JSON 형식으로 쓴다. 다른 스킬의 기준을 evaluator 안에 두지 않는다. 덮어쓰기 전에 `eval_criteria.yaml.backup-<UTC timestamp>`를 배타적으로 생성한다. 실행에는 불변 사본과 해시를 남긴다.

최상위에 이식 가능한 `default_working_directory`(`.` 또는 `~/...`)와 필수 `test_cases`를 둔다. 디렉터리를 생략하면 현재 검증기는 `.`을 쓴다. 우선순위는 사례 working_directory > 최상위 기본값 > `.`(빈 격리 sandbox)이다. 명시적 상대 디렉터리는 대상 소스 기준으로 해석하고 evaluator가 소유한 신뢰할 수 있는 scaffold가 데이터로 복사한다. 사용자 프로젝트 설정을 실행하지 않는다. 재사용 기준에 `/Users/name`, `/home/name` 같은 개인 절대 경로를 넣지 않는다. `target_skills`는 저장소 상대 SKILL.md 경로다.

```yaml
default_working_directory: .
test_cases:
  - id: TC-001
    name: 인사말 자연 호출
    category: invocation
    project: observatory-greeting
    target_skills: [observatory-greeting/SKILL.md]
    working_directory: .
    prompt: Observatory 팀에서는 새 기여자에게 어떻게 인사하나요?
    description: 자연스러운 요청으로 정상적인 스킬 발견을 검사한다.
    expected_behavior: 인사말 스킬을 호출하고 정확한 팀 규칙을 제시한다.
    eval_target: all
    expect_invocation: true
    timeout_seconds: 120
    max_turns: 8
    quality_criteria:
      required_present: [Welcome to Observatory.]
      required_absent: []
      semantic_checks:
        - question: 에이전트가 문서에 정해진 인사말을 정확히 제시했는가?
          weight: 3
          critical: true
          rubric:
            5: 정확한 인사말과 적절하고 간결한 맥락을 제시한다.
            4: 인사말은 정확하지만 작은 불필요한 설명이 있다.
            3: 정확한 인사말과 사용할 수 있는 설명을 제시한다.
            2: 인사말 규칙이 불완전하다.
            1: 인사말이 틀리거나 없다.
      artifact_checks: []
```

Binary 검사는 **오직** `rubric: {1: "관찰 가능한 PASS 조건", 0: "관찰 가능한 FAIL 조건"}`을 쓰며 weight는 양수다. 모든 사례에 관찰 기준을 갖춘 의미 검사가 최소 하나 있어야 한다. 선택적 `critical: true`는 Binary 1 또는 Likert >=3을 요구하며 실패하면 최종 통과를 막는다. `required_present`/`required_absent`는 **출력**의 정확한 문구 제약이므로 의미상 반드시 필요한 문구만 넣는다. `eval_target: response`는 assistant 최종 출력, tool_usage는 실제 호출, artifact는 수집 파일, all은 이들을 합친다. 사용자 프롬프트나 주입된 지침을 출력으로 검사하지 않는다.

`artifact_checks: [{path: result.md}]`는 성공 주장 링크가 아니라 실제 수집 파일을 요구한다. 없으면 실패다. 비텍스트 산출물은 검증된 도메인 렌더러로 확인한 뒤 채점한다. 바이너리 바이트를 임의로 디코딩해 의미 있는 증거로 취급하지 않는다.

모드별 정수 배분 순서는 `invocation / efficiency / best_practices / business_impact / task_completion`이다.

- BASIC: **1/1/1/1/0**, 정확히 4개.
- THOROUGH: **2/1/2/2/3**, 정확히 10개. 원래 요청된 백분율 범위는 정수 10개로 동시에 만족할 수 없다(허용 최대 합계 9). 나머지 1개를 완수에 배정해 30%로 둔다.
- Deep/comprehensive: **7/4/7/5/7**, 30개로 요청된 모든 비율을 만족한다.

Invocation은 자연어로 작성하고 `/skill-name`, 강제 맥락, 정답 누출을 금지한다. 사례 수가 허용하면 긍정, 부정(`expect_invocation: false`), 모호성, 인자 추론을 포함한다. 다른 범주는 `forced_context: true`(기본값)로 정상 세션에 스킬 사용을 요청할 수 있다. 완수 사례는 정상 경로, 누락·없는 대상, 복잡한 입력, 생략 압박·충돌 지시, 산출물, 복구 가능한 의존성 오류를 다룬다. 10개 모드에서 모두를 별도 완수 사례로 만들 수는 없으므로 다른 범주에도 분산하고 전체 커버리지는 deep을 사용한다.

## Mock 계약

`intercept_patterns`는 Bash 정규식 **전체 일치** 목록이다. `mock_data[pattern]`에는 stdout, stderr, exit_code가 있다. Native PreToolUse hook은 일치한 Bash 입력만 셸 인용된 고정 stdout/stderr와 지정 종료 코드로 바꾸며 원래 명령은 실행하지 않는다. 미일치 명령은 `UNMOCKED_EXTERNAL_CALL`로 거부한다. 무해한 무작위 표식 probe가 현재 runner의 hook 지원을 먼저 확인하며 실패하면 실제 사례를 실행하지 않는다. 고정 응답 문자열을 셸 코드로 실행하지 않는다. 미지원 기능은 mock 통과가 아니다.

`intercept_mcp_tools`는 확인된 정확한 런타임 이름(`mcp__server__tool`)이다. 대응하는 mock_data에는 response, input_schema, description, 선택적 expect/error, `runtime_name_verified: true`와 조사 출처 `runtime_name_source`를 넣는다. 이름·스키마는 실제 tools/list에서 얻고 alias로 추론하지 않는다. 어댑터가 native `evals/mocks/<server>/<tool>.md`와 `_tools.json`을 만든다. 실제 서버는 차단한다(`--mocks record`; `--allow-real-servers` 사용 안 함). 런타임 불일치·오류는 환경 실패다. 호출 가로채기를 설정하면 mock_data는 필수다.

test_cases 옆 선택적 `analysis`는 재사용 기준에 대한 검토된 동작 분석이다. 발견 단계 필드와 `mutates: true|false`, mutation_evidence를 포함한다. 모르는 동작을 읽기 전용으로 간주하지 않는다. 생성된 작성자 분석은 별도 보존한다.

맥락 검사에는 지식 질문을 쓴다('스킬 X를 사용할 때 어떤 규칙을 따라야 하나요?'). 실제 산출물·완수 검사는 실행을 요청한다. 동작 검사는 스킬 이름을 언급하고 invocation은 강제 라우팅하지 않는다. A/B의 환경·모델·기준을 고정한다. 3라운드는 변동을 줄이지만 무편향·정답을 입증하지 않는다. 중첩 evaluator 검사는 근거 있는 900초 제한과 범위가 정해진 fixture를 사용하며 무한 재귀 평가하지 않는다.

## 필드 설명

아래는 `validate_criteria`가 받는 이식 가능한 파일이며 native runner의 별도 사례 스키마가 아니다. 어댑터가 native 사례로 변환한다.

| 필드 | 유형 / 기본값 | 계약 |
|---|---|---|
| `default_working_directory` | string, 기본 `.` | 공유 기준에는 명시하는 편이 좋다. `.`은 호출자의 checkout이 아닌 빈 격리 sandbox다. |
| `test_cases` | 비어 있지 않은 list | 모드의 정확한 범주 배분과 고유 ID. |
| `analysis` | 선택적 object | 재사용할 검토된 분석. boolean `mutates`와 변경 근거를 포함한다. 없으면 준비 단계가 작성자 분석을 실행한다. |
| `id` | string | `TC-`와 숫자 3개. 예: `TC-001`. |
| `name` / `description` | string | 사람이 읽을 동작 이름과 이 사례만의 차이. |
| `category` | enum | `invocation`, `efficiency`, `best_practices`, `business_impact`, `task_completion`. |
| `project` | string | 대상 frontmatter name. 라우팅 검사는 관찰한 Skill 호출과 비교한다. |
| `target_skills` | 상대 경로 list | 최소 1개, 절대 경로·`..` 금지. 실제 저장소 상대 `SKILL.md` 위치를 기록한다. 실행 대상은 발견 단계가 확정한 단일 스킬이다. |
| `working_directory` | 선택적 string | 기본값을 덮어쓴다. 명시적 디렉터리는 fixture 데이터로 복사하며 원본을 reset/switch/clean하지 않는다. |
| `prompt` | 비어 있지 않은 string | 실제 평가 입력. invocation은 슬래시 명령·강제 스킬 본문 없는 자연어다. |
| `expected_behavior` | string | 중요한 실패 동작을 포함한 관찰 가능 결과. |
| `eval_target` | enum | `response`, `artifact`, `tool_usage`, `all`. 내용 검사·인용의 근거가 될 출력을 정한다. |
| `expect_invocation` | boolean, 기본 `true` | invocation의 부정 사례는 `false`. |
| `forced_context` | boolean | invocation에서 true 금지. 다른 범주는 기본적으로 정상 세션에 설치 스킬 사용을 요청한다. |
| `timeout_seconds` | integer, 기본 runner 제한 | 1~3600초. 중첩 검사는 명시적이고 정당한 예산이 필요하다. |
| `timeout_reason` | 선택적 string | 늘린 중첩 검사 시간의 이유이며 기준 출처로 보존한다. |
| `max_turns` | integer, 어댑터 기본 15 | native 세션 제한. 과제에 맞는 작은 양수 예산. |
| `quality_criteria` | object | 필수 배열 4개: `required_present`, `required_absent`, `semantic_checks`, `artifact_checks`. |
| `semantic_checks[].question` | 비어 있지 않은 string | 직접 채점 가능한 관찰 질문. |
| `semantic_checks[].weight` | 유한한 양수 | 별도 보고하는 의미 검사 가중 점수에 사용. |
| `semantic_checks[].rubric` | map | Likert는 정확히 정수 키 1~5, Binary는 0/1. 각 값은 관찰 가능한 동작 수준. |
| `semantic_checks[].critical` | boolean, 기본 `false` | 실패하면 차원 종합 점수와 무관하게 사례 FAIL. |
| `artifact_checks[].path` | 상대 string | 필수 수집 파일, 경로 탈출 금지. 추가 도메인 검사는 의미 루브릭이나 검증된 렌더러에 둔다. |
| `artifact_checks[].sha256` | 선택적 64자리 hex string | 수집 파일의 기대 SHA-256. 불일치는 결정적 critical 실패다. 바이트 단위로 그대로 유지돼야 하는 보호 파일에 쓴다. 존재만으로는 보존이 아니다. |
| `intercept_patterns` | 선택적 regex string list | 전체 일치 Bash 가로채기. mock_data에 대응 항목 필요. |
| `intercept_mcp_tools` | 선택적 런타임 이름 list | 실제 목록으로 확인된 정확한 `mcp__server__tool`. |
| `mock_data` | 선택적 mapping | 가로채기가 있으면 필수. 비밀·실제 자격 증명을 넣지 않는다. |

`~/project/fixtures` 같은 문자열 경로는 같은 fixture를 같은 위치에 준비했을 때만 홈 간 이식 가능하다. 내용까지 같다는 보장은 아니므로 비교 시 입력·환경 버전을 기록한다.

## Binary 사례 예시

4·10·30개 모음에 포함할 단일 사례다. 혼자 실행하면 의도된 범주 개수 검증에 실패한다.

```yaml
id: TC-001
name: 인사말 자연 호출
category: invocation
project: observatory-greeting
target_skills: [observatory-greeting/SKILL.md]
prompt: Observatory 팀에서는 새 기여자에게 어떻게 인사하나요?
description: 자연 라우팅과 인사말 계약을 검증한다.
expected_behavior: 대상 스킬을 호출하고 문서에 정해진 인사말로 답한다.
eval_target: all
expect_invocation: true
quality_criteria:
  required_present: [Welcome to Observatory.]
  required_absent: []
  semantic_checks:
    - question: 문서에 정해진 인사말을 응답했는가?
      weight: 3
      critical: true
      rubric:
        1: 인사말을 정확히 제시했다.
        0: 인사말이 틀리거나 없다.
    - question: 요청한 인사 규칙에만 설명을 한정했는가?
      weight: 1
      rubric:
        1: 관련 내용에 집중해 간결히 답한다.
        0: 무관한 절차나 과제를 추가한다.
  artifact_checks: []
```

## Bash mock 예시

실제로 이 명령 하나가 필요한 사례에 추가한다. 격리 fixture이며 실제 CLI 계약이 아니다.

```yaml
intercept_patterns:
  - 'teamctl status --json'
mock_data:
  'teamctl status --json':
    stdout: '{"state":"ready"}\n'
    stderr: ''
    exit_code: 0
```

MCP의 input_schema는 실제 runtime tools/list에서 얻는다. 문법상 그럴듯한 이름이나 근거 없이 쓴 `runtime_name_verified: true`는 검증이 아니다. runtime_name_source에 목록의 출처를 보존하고 실행 뒤 도구 호출 trace를 확인한다.
