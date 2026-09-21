# skill-evaluator

실행 근거를 보존하는 Claude Code 스킬 평가 도구다. 스킬을 찾고 재사용 가능한 기준을 준비한 뒤, 설치된 Claude Code native eval runner에 실행을 맡긴다. 독립 채점 세션이 보존된 근거를 평가하고 서로 연결된 로컬 보고서를 만든다.

로컬 실행은 `claude plugin eval` 위에 구현되어 있다. 별도의 에이전트 실행 프레임워크를 만들지 않는다. MSL Judge, SkillWatch, PixelCloud는 실제 서비스의 현재 help/schema에 맞춘 운영자 bridge가 필요하다. 이 문서에 이름이 있다는 이유만으로 내부 서비스 연동이 작동하는 것은 아니다.

## 설치와 환경 확인

`SKILL.md`는 scripts와 references를 사용하므로 `skill-evaluator/` 전체를 함께 둔다. [jha0313/skills_repo](https://github.com/jha0313/skills_repo) checkout에서 호스트의 일반 스킬 설치 방식을 사용하거나, 대상 경로가 없을 때 폴더 전체를 `~/.claude/skills/skill-evaluator`로 복사한다. 기존 설치의 변경 사항을 보존하지 않고 덮어쓰지 않는다. 아래 CLI는 설치 없이 저장소 루트에서도 실행할 수 있다.

필수 환경: Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/), 필요한 native eval flag가 help에 있는 인증된 Claude Code. `uv run`이 고정된 `PyYAML==6.0.3`을 격리 환경에 설치한다. 일반 `python3` 실행은 이 의존성을 별도 설치해야 한다.

```bash
uv run skill-evaluator/scripts/evaluate.py doctor
```

Claude Code가 없으면 공식 [설치 안내](https://code.claude.com/docs/en/setup)를 따른다. 설치되어 있지만 native eval 기능이 없으면 `claude update` 후 `claude plugin eval --help`를 확인한다. 인증은 `claude auth login`이다. 개발 당시 2026-09-19의 CLI는 2.1.275였지만 호환성은 그 과거 버전으로 추정하지 않고 시작 때 확인한다.

내장 발견·보고서 도우미가 없으면 패키지가 불완전하다. 새 디렉터리에 `git clone https://github.com/jha0313/skills_repo.git` 후 전체 스킬 폴더를 다시 설치한다. 이 도우미는 사용할 수 없는 내부 template-discovery·visualization 의존성을 대신한다.

## 빠른 실제 평가 두 가지

저장소 루트에서 실행한다. 포함된 작은 인사말 fixture를 **실제 에이전트와 독립 채점자**로 평가하므로 인증 계정의 모델 사용량이 발생한다. SkillWatch나 PixelCloud는 호출하지 않는다.

BASIC: 정확히 4개 사례.

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --basic --local --criteria skill-evaluator/tests/fixtures/basic.yaml --trust-target --no-visualize
```

기본 THOROUGH: 10개 사례, 로컬 HTML 생성.

```bash
uv run skill-evaluator/scripts/evaluate.py run skill-evaluator/tests/fixtures/observatory-greeting --local --criteria skill-evaluator/tests/fixtures/thorough.yaml --accept-criteria --trust-target
```

`--trust-target`은 대상과 상위 plugin 코드가 이미 호스트 사용자의 승인된 신뢰 범위 안에 있다는 확인이다. Bash, Write/Edit, 네트워크 도구, 실제 MCP, 발행 권한을 추가하지 않는다. 지정 전에 fixture와 기준을 읽는다. `--accept-criteria`는 제시된 기준을 실행하기로 한 호스트 결정을 기록하며 미확인 기준의 검토를 대신하지 않는다.

스킬 사례 실패는 종료 코드 1, 설정·환경·발행 오류는 2, 중단은 체크포인트를 보존하고 130이다. 실행 완료 후 0은 전체 통과를 뜻한다. 다만 `prepare`·`validate`도 실제 평가 없이 0을 반환하므로 명령과 보고서 상태를 함께 읽는다.

## 설치된 스킬 평가

```bash
uv run skill-evaluator/scripts/evaluate.py prepare TARGET --local
```

고유한 설치 이름이나 SKILL.md가 있는 정확한 디렉터리를 지정한다. 설치 읽기 경로가 plugin 캐시라면 `--source /path/to/writable/skill`을 사용한다. 기준은 **대상** 소스 옆에 쓰고 덮어쓰기 전에 타임스탬프 백업을 만든 뒤 검토 표를 출력한다. 원본 working copy를 reset/clean하지 않는다.

기준을 검토·수정한 뒤:

```bash
uv run skill-evaluator/scripts/evaluate.py run TARGET --local --criteria /path/to/writable/skill/evals/eval_criteria.yaml --accept-criteria --trust-target
```

준비한 실행이 변경되지 않았다면 검토 후 재개할 수도 있다.

```bash
uv run skill-evaluator/scripts/evaluate.py run --resume ~/skill-eval/TARGET/RUN-ID
```

재개는 저장된 옵션·기준·해시를 사용하므로 새 평가 flag를 추가하지 않는다. 스킬·evaluator·기준·어댑터 설정이 바뀌면 새 실행이 필요하다. 완료된 사례 실행과 유효한 채점 체크포인트는 재사용한다.

## 모드와 옵션

| 옵션 | 동작 |
|---|---|
| `--basic` | 호출·효율·모범 사례·업무 효과 각 1개, 총 4개. 전용 완수 사례는 없다. |
| 크기 flag 없음 | 기본 THOROUGH: 5개 차원에 걸친 10개 사례. |
| `--deep` / `--comprehensive` | 30개. 대화에서 명시적으로 thorough/deep/comprehensive의 깊이를 요청하면 여기에 대응한다. 별도 `--thorough` CLI flag는 없다. |
| `--binary` | 가중 이진 의미 검사와 PASS/FAIL. 기본은 Likert 1~5. |
| `--local` | 설정된 MSL bridge를 건너뛰고 native 로컬 격리를 사용한다. |
| `--no-visualize` | HTML·PixelCloud 생략. Markdown/JSON과 선택한 SkillWatch는 유지한다. |
| `--model MODEL` | 평가 대상 모델 선택. |
| `--judge-model MODEL` | 독립 작성자·채점 모델 선택. 저장소 승인 기본값이 없으면 인증된 CLI 기본값을 따르고 기록한다. |
| `--concurrency N` | 1~8, 기본 3. 변경 동작은 사례를 강제로 순차 실행한다. |
| `--judge-rounds N` | 1/3/5, 기본 3. 같은 실행 근거를 독립 세션에서 채점한다. |
| `--timeout SECONDS` | 대상 기본 300초, 사례별 값 우선, 최대 3600초. |
| `--judge-timeout SECONDS` | 작성자·채점 프로세스별 기본 300초, 최대 3600초. |
| `--allow-tool TOOL` | 승인된 과제에 필요한 도구의 명시적 허용. 반복 가능. |
| `--reuse-criteria` | 기존 대상 기준을 명시적으로 재사용. BASIC은 여전히 표준 4개가 필요하다. |
| `--config FILE` | 현재 계약 출처가 있는 선택적 운영자 bridge 설정. |

발견 단계는 실제 변경 동작을 분석한다. 읽기 전용 사례는 동시 실행할 수 있고 변경 스킬은 깨끗한 native sandbox에서 순차 실행한다. Invocation은 새 세션의 정상 스킬 발견을 사용한다. 스킬 맥락을 명시적으로 로드하는 방식은 다른 범주에서만 허용하고 기록한다.

[사례 스키마·모킹](references/test_case_format.md), [Likert 루브릭](references/grading_rubric.md), [Binary 루브릭](references/grading_rubric_binary.md), [결과·bridge 스키마](references/result_schema.md), [보고서 계약](references/report_template.md)을 참고한다.

## 보존하는 파일

기본 실행 위치는 `~/skill-eval/<skill-name>/<run-id>/`다.

- `manifest.json`, `analysis.json`, `criteria.yaml`, `CRITERIA_REVIEW.md`, 수집한 native CLI help.
- `cases/TC-001/`: 프롬프트, 전체 실행 기록, native trace, 출력만 담은 응답, 실제 도구 호출, metadata, 산출물, 정규화 실행, 어댑터 로그.
- `judges/`: 독립 채점 입력·결과 원문과 검증된 체크포인트.
- `evaluations/TC-001.md/.json`: 정확한 근거 인용, 일치한 루브릭 수준, 결정적 검사 결과.
- `summary.json`, `REPORT.md`, 선택적 `REPORT.html`: 합계, 세부 결과, 실패, 개선안, 근거 링크.

미확인 사용량·비용은 null이며 CLI 추정치는 청구서가 아니다. 대상·채점·작성 비용을 따로 보존하므로 실행·채점 합계와 `author_cost_usd`를 함께 확인한다. 병렬 실행의 사례별 시간 합은 실제 경과 시간과 다르다.

사례 대표 범주는 커버리지 라벨이다. 채점자는 그 실행의 모든 선택 차원을 채점한다. 의미 검사 가중 점수는 진단용이며 `critical: true`는 필수 의미 검사 실패가 통과 종합 점수를 무효화하게 한다. 전체 최종 판정은 모든 사례 통과를 요구한다. 점수·필수 조건 실패·환경 오류를 함께 읽는다.

## A/B로 추가 가치 확인

`compare RUN_A RUN_B`는 기존 정규화 실행 두 개를 비교한다. 무스킬 대조군을 자동 실행하지 않는다. 기준 해시만 같다고 모델·fixture·도구·환경까지 같다고 할 수 없다.

실제 스킬 사용 유무 비교는 native runner의 현재 ablation 지원을 재사용한다. 중립적인 과제 프롬프트, 같은 fixture와 도메인 채점기를 가진 신뢰할 수 있는 native plugin 사례를 준비한다. 대조군에 스킬 이름·본문을 강제하지 않는다. 이 orchestrator의 '출력이 비어 있지 않음' 수집 채점기만으로 품질을 측정하지 않는다. 아래 출력 경로가 적절한 디렉터리에서 실행한다.

```bash
claude plugin eval /path/to/trusted-plugin --ablation with-without --runs 3 --concurrency 1 --mocks record --no-publish --keep-temp --json ab-result.json --output-dir ab-results
```

이 명령은 대조군별 대상 실행 3회이며 한 기록에 대한 독립 채점 3회가 아니다. Native plugin 자체 grader 스키마·집계 형식은 이 orchestrator의 정규화 결과와 다르다. 두 조건의 원시 trace를 보존하고 같은 근거 기반 도메인 기준으로 완수·토큰·실제 경과 시간을 비교한다. 검증된 정규화 변환 없이 native 보고서를 `compare`에 직접 넣을 수 없다.

업무 효과 루브릭으로 실제 시간 절감·매출·인과적 생산성을 주장하지 않는다. 과제, 시작 revision, 모델·예산, mock, 완수 임계값을 고정하고 반복 또는 실행 순서를 바꿔 변동을 확인한다. 미완성 때문에 토큰이 적은 것은 효율 향상이 아니다.

## 내부 서비스와 발행

기본은 로컬 실행이다. `--publish-skillwatch`·`--publish-pixelcloud`에는 별도 명시적 선택과 설정된 bridge가 필요하다. 프로젝트 생성은 추가로 `--create-project`가 필요하다. Bridge는 호스트 권한을 보존하고 실제 서비스 스키마를 검증하며 run ID를 멱등 키로 강제해야 한다. 비공개 endpoint나 `fbcode//msl/judge:run_eval` flag를 추측하지 않는다.

정규화 bridge로 MSL 우선·fallback을 지원한다. 첫 사례의 MSL 환경 오류는 로컬 재시도할 수 있지만 실제 스킬 실패는 어댑터 변경 이유가 아니다. 실제 MSL/SkillWatch/PixelCloud 연동은 결정적 mock bridge 테스트와 구분해 보고한다.

## 명세 차이와 한계

- 요청된 비율을 정수 10개로 모두 만족할 수 없다(허용 최대 합계 9). 기본 **2/1/2/2/3**은 완수 30%를 우선하며 deep **7/4/7/5/7**은 범위를 만족한다.
- 저장소에 승인된 고품질 채점 모델 설정은 없다. 명시하지 않으면 CLI 기본값을 따르고 기록하며 '저장소 승인'이라고 부르지 않는다.
- 내장 발견·HTML 도우미가 없는 내부 도구를 대신한다. 내부 서비스는 운영자 bridge를 사용하며 인터페이스·mock 계약만으로 실제 연동을 입증하지 않는다.
- 비텍스트 산출물은 도메인 렌더러가 필요하다. 파일 이름·바이너리 바이트만 보고 이미지·PDF·실행 동작을 검사했다고 주장하지 않는다.
- 도구 mock은 의존성 재현성을 높일 뿐 LLM을 결정적으로 만들지 않는다. 채점 3라운드는 일부 변동을 줄이지만 진실·공통 편향 제거를 보장하지 않는다.
- 일반 sandbox가 모든 plugin을 변경 없이 실행한다고 보장할 수 없다. 미지원 의존성은 실제 환경 사본 또는 명확한 오류로 드러내고 점수를 지어내지 않는다.

검증 결과는 특정 코드 revision과 보존한 실행에 속한다. 성공적으로 평가됐다고 설명하기 전에 최종 manifest와 보고서를 읽는다.

## 개발 당시 기록된 검증

다음은 **한국어 현지화 이전**, 2026-09-19 Claude Code 2.1.275에서 수행한 기록이다. 과거 결과·원문은 번역하지 않았으며 이 기록이 한국어판의 실제 모델 실행 검증을 대신하지 않는다.

- 결정적 회귀 31개 통과: 중단, 기준 백업, 정확한 배분, 프롬프트·다른 사례 근거 거부, 누락·변경 산출물, 발행 멱등성, Binary 임계값, 제한된 스키마 교정.
- Ruff lint/format과 mypy 통과. 관련 PR·push의 저장소 workflow가 모델 인증 없이 결정적 검사를 반복한다.
- 실제 BASIC Likert 4/4, 기본 THOROUGH 10/10 통과. 각 실행을 독립적으로 3번 채점했다. 실행·채점 CLI 추정 비용은 각각 약 $2.21/$5.42였으며 청구서나 임의 스킬의 비용 예측이 아니다.
- 실제 Skill 도구가 자연어 읽기 전용 설명 요청에서 skill-evaluator를 호출했다.
- 실제 native Bash PreToolUse가 원래 명령 대신 고정 표식을 반환했다. 실제 native MCP 대역은 정확한 mock 조회 1회를 실행했고 미모킹 호출은 없었다. 둘 다 fixture이며 실제 외부 서비스 작업이 아니다.
- SkillWatch는 결정적 가짜 bridge로만 검사했다. 실제 MSL Judge·PixelCloud 연동은 실행하지 않았다.

초기 실제 실행에서 계산된 차원의 소수 검증 문제, 기준 작성에서 Binary/Likert critical 혼합 문제가 발견됐다. 잘못된 출력은 점수를 주지 않고 환경 오류로 보존했다. 현재 계산 차원은 중앙에서 다시 계산하며 기준 작성은 기록이 남는 스키마 교정 1회만 허용한다. Fixture 통과는 실행한 경로를 검증할 뿐 모든 설치 스킬·도메인의 정답성을 보장하지 않는다.

## 한국어 사용 범위

스킬 설명, 기준 작성·독립 채점 지시, 새 사례의 프롬프트·루브릭, CLI 안내, 로컬 보고서 화면은 한국어다. `SKILL.name`, 명령·flag, 스키마 키·enum, 점수 공식·임계값, 계약상 정확한 문구, 공급자 원시 출력, 과거 실행 기록은 유지한다. 새 채점 이유는 한국어로 쓰되 evidence.quote는 원문 그대로 남긴다. 포함된 인사말 fixture의 계약 문구 `Welcome to Observatory.`도 번역하지 않는다.

한국어 현지화에서는 기존 회귀31개와 보고서의 원문·기계 필드·미확인 값·escaping 보존 검사1개, 총32개가 통과했다. Ruff lint/format, mypy, BASIC/Binary/THOROUGH 예시 형식 검증도 통과했다. 한국어판의 새 실제 모델 평가나 브라우저 시각 검증은 실행하지 않았다. Codex의 기본 skill validator는 기존 Claude 전용 `argument-hint`를 허용하지 않으므로 해당 두 스킬은 그 차이를 보존하고 YAML·이름·도구·인자 계약을 별도로 검증했다.
