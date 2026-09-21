# 정규화 결과와 bridge 계약

정규화 실행, 사례별 평가, 실행 명세, 집계는 `schema_version: skill-evaluator/1`을 쓴다. 원시 도구·CLI 응답과 말단 metadata/artifact 파일은 자체 형식을 보존한다. 두 어댑터 모두 `normalize_execution`을 거친다. 외부 bridge는 **확인된** 내부 출력을 이 계약으로 변환해야 하며 Meta 필드를 추측하지 않는다. 이 저장소·환경에는 MSL Judge, SkillWatch 스키마, PixelCloud 업로드 계약이 없으며 설치·작동했다고 주장하지 않는다. 2026-09-19 확인한 Claude Code 2.1.275의 native CLI help/source는 로컬 격리·라우팅·mock·원시 출력을 제공했다. 실제 사용 시 현재 help를 다시 확인한다.

## 실행 계약

```json
{"conversation":"전체 실행 기록", "response":"assistant 최종 출력만", "tool_calls":[{"name":"Skill","input":{"skill":"plugin:example"}}], "metadata":{"model":"실제 실행 모델","started_at":"ISO8601","finished_at":"ISO8601","duration_seconds":1.2,"exit_state":"completed","timed_out":false,"usage":{"input_tokens":100,"output_tokens":20,"cache_read_input_tokens":0,"cache_creation_input_tokens":0},"cost_usd":null,"cost_basis":"unavailable","skill_invocations":["plugin:example"]},"artifacts":{"files":[{"path":"report.md","exists":true,"sha256":"...","evidence_path":"cases/TC-001/artifacts/report.md","content":"실제 파일 내용"}],"urls":[]}}
```

미확인 수치·비용은 null이다. 어댑터는 인용할 모든 파일을 사례 디렉터리에 생성한다. 경로 탈출과 심볼릭 링크는 거부한다. 충분한 원시 trace·산출물 근거가 없는 MSL 출력은 ERROR다. response에 사용자 프롬프트나 주입된 지침을 넣지 않는다. Native의 `out/trace.jsonl`을 복사하되 비공개 runtime 설정은 복사하지 않는다. 보존한 `sealed/home/cwd`는 데이터 확인을 위해서만 열고 다시 봉인한다. 그 안에서 git·hook·설정을 실행하지 않는다. 실행 기록에서 찾은 URL은 '언급'으로 표시하며 접근 가능하거나 발행에 성공했다고 단정하지 않는다.

사례 저장: `cases/TC-ID/conversation.txt`, `trace.jsonl`(native), `prompt.json`, `response.txt`, `tool_calls.json`, `metadata.json`, `artifacts.json`, `artifacts/*`, `execution.json`, 어댑터 원시 stdout/stderr/JSON. 사례 결과: `evaluations/TC-ID.json`과 `.md`.

평가 JSON은 case_id/name/category, grading, status(`graded|error`), score(환경 오류 시 null), verdict(`PASS|FAIL|ERROR`), 선택적 Likert grade, critical_failure, dimensions, Binary dimension_verdicts, 모범 사례 6항목, 업무 효과 5항목, 의미 검사·가중 점수, 결정적 문구·산출물·라우팅 검사, 원시 judge_rounds, metadata, 채점 비용·배분, 근거 링크를 포함한다. 각 채점 항목은 rubric_level, reason, `evidence:[{path,line_start,line_end,quote}]`를 갖는다. 경로는 해당 사례 출력·산출물 허용 목록으로 제한하며 채점 전 정확한 인용문·줄을 검증한다.

실행 명세는 evaluator_version, run_id, created_at, state, skill(설치·소스 경로, revision, 내용 해시), 전체 analysis, criteria_hash, 타임스탬프 백업 경로, 확정 옵션, 어댑터 설정·해시·출처, CLI help/version, execution_adapter, 가격 설정, 작성자 사용량, 사례별 상태, 발행 영수증·상태를 기록한다. 상태는 criteria_review→executing→grading→reported→complete/incomplete이며 중단 시 체크포인트를 보존한다. 원자적 쓰기와 실행별 잠금이 중복 runner를 막는다. 소스·기준·evaluator·bridge 설정 변경 시 재개를 거부하고, 유효한 실행·채점 체크포인트는 재사용한다.

집계 `summary.json`은 전체/통과/실패/오류/통과율, 점수·분포, 범주·차원·모범 사례 세부 결과, 비용·토큰·시간, 확인된 비용 소계, 작성 비용, 실패 유형, ID별 개선안, 사례 결과를 담는다. CLI 비용은 **정가 추정치**이며 청구액이 아니다. 실행·채점 비용은 별도이며 채점 batch 비용은 사례에 균등 배분하고 원시 batch 사용량을 보존한다. 모르는 구성 요소의 합계는 null이다.

## 검증된 내부 bridge(선택)

설정 JSON은 `msl`, `skillwatch`, `pixelcloud`를 다음과 같이 매핑한다.

```json
{"command":["/absolute/path/to/your-verified-bridge"],"contract_provenance":"현재 내부 --help와 schema의 출처, revision/날짜"}
```

Bridge 실행 파일은 JSON 요청 하나를 stdin으로 받고 JSON 응답 하나를 stdout으로 반환하며 셸 보간은 하지 않는다. 시간 제한을 두고 stdout/stderr/request/response를 보존한다. 설치·인증은 운영자 환경에서 준비한다. **실제 서비스가 있는 환경 안에서** `fbcode//msl/judge:run_eval` help와 SkillWatch/PixelCloud 스키마를 확인한 뒤 최소 변환부를 구현한다. 가짜 bridge 설정은 테스트 fixture일 뿐이다.

MSL `execute` 요청은 schema_version, operation, run_id, case, analysis, options를 포함한다. 응답은 `{"status":"ok","execution":<위 정규화 결과>}`다. 첫 사례의 환경 오류면 이유를 보존하고 native local로 한 번 전환한다. 정상 실행의 실패 판정은 테스트 실패로 유지한다. MSL bridge가 없으면 곧바로 native local을 쓴다.

발행 요청은 run_id, idempotency_key=run_id, summary, report_path, create_project를 포함한다. 응답은 `{"status":"ok","idempotency_key":"같은 run id","url":"..."}`여야 한다. `--publish-skillwatch`/`--publish-pixelcloud`의 명시적 선택 때만 호출한다. 프로젝트 생성에는 `--create-project`가 필요하며 bridge가 멱등성을 보장해야 한다. 영수증은 payload hash를 캐시해 같은 실행을 다시 발행하지 않는다. 네트워크 결과가 불확실할 때도 bridge/서버가 같은 키를 보장해야 한다. 발행된 집계가 바뀌면 새 실행이 필요하다. 실패를 성공으로 기록하지 않는다. `--no-visualize`는 로컬 HTML/PixelCloud를 생략하고 Markdown/JSON과 선택한 SkillWatch는 유지한다.

## 검증 경계

MCP mock은 native runner가 받는 디렉터리 스키마를 쓰며 Meta intercept flag를 지어내지 않는다. Bash mock은 실제 native PreToolUse hook probe가 통과해야 하고 알 수 없는 명령은 차단한다. 기본 fixture에는 실제 MCP 서비스나 제한 없는 실제 Bash가 필요하지 않다. 상위 plugin 맥락을 몰래 제거하지 않는다. Plugin의 로컬 스크립트·위임 구성 요소에는 지원되는 실제 사본 환경 또는 조치 가능한 의존성 오류가 필요하다. 바이너리 산출물 채점에는 렌더러가 필요하다.

## 필드별 스키마

아래는 evaluator가 유지하는 정규화·버전 관리 레코드다. 공급자별 세부 정보는 보존된 native JSON에서 확인하며 어댑터 변환 중 그 근거를 버리지 않는다.

### `execution.json`과 사례 근거

| 필드 | 유형 | 의미 |
|---|---|---|
| `schema_version` | string | `skill-evaluator/1`. |
| `conversation` | string | 입력 출처를 포함한 전체 수집 대화·trace. 그 자체는 정답 인용에 허용되지 않는다. |
| `response` | string | 실제 평가 대상 assistant 출력. 기준·주입된 스킬 내용은 제외한다. |
| `tool_calls` | array | name/input이 있는 실제 도구 호출. native ID는 선택적이다. |
| `metadata.model` | string 또는 null | 보고된 실제 실행 모델. 요청만 한 모델을 실행 모델로 만들지 않는다. |
| `metadata.started_at`, `finished_at` | timestamp | 기록된 실행 시작·종료 시각. |
| `metadata.duration_seconds` | number | 관찰된 사례별 실행 시간. |
| `metadata.exit_state`, `timed_out` | string, boolean | 완료·오류·시간 초과는 채점 판정과 별개다. |
| `metadata.usage` | object | 입력/출력/cache-read/cache-creation 토큰. 미확인 값은 null. |
| `metadata.cost_usd`, `cost_basis` | number 또는 null, string | 공급자 추정치와 공급자·버전 출처. 실제 청구액 아님. |
| `metadata.adapter` | string | 정규화 어댑터 식별자. |
| `metadata.skill_invocations` | string array | 라우팅 검사에 사용한 실제 Skill 호출. |
| `metadata.permission_denials`, `error`, `mock_status` | 선택적 공급자 데이터 | 권한·mock·환경 실패를 드러내기 위해 보존. |
| `artifacts.files` | array | 수집 경로·존재 여부, 있으면 내용/해시/바이트/근거 경로, 없으면 오류. |
| `artifacts.urls` | array | URL과 출처. 기록에 언급된 것만으로 접근 가능·발행 성공을 입증하지 못한다. |

산출물 `path`는 sandbox 상대 생성 경로, `evidence_path`는 실행 디렉터리 상대 경로다. `artifacts/*`에는 복사된 바이트가 있다. 응답이 파일 이름을 주장하는 것과 실제 수집은 다르다. 크기 한도·symlink 거부·렌더러 한계는 필수 근거를 조용히 생략하는 대신 명시적인 실패로 드러낸다.

### `evaluations/TC-001.json`

| 필드 | 유형 | 의미 |
|---|---|---|
| `case_id`, `name`, `category` | string | 안정적인 사례 식별자·이름·커버리지 범주. |
| `grading` | enum | 채점 사례의 `likert` 또는 `binary`. |
| `status` | enum | `graded` 또는 `error`. |
| `score` | number 또는 null | 차원 종합 점수. 환경 오류에는 점수가 없다. |
| `verdict` | enum | `PASS`, `FAIL`, `ERROR`. |
| `grade` | 선택적 string | Likert에서만 반올림 전 점수에 따른 A/B/C/D/F. |
| `critical_failure` | boolean | 필수 내용·의미·라우팅·산출물 실패가 있으면 통과를 막는다. |
| `dimensions` | mapping | BASIC 4개 또는 THOROUGH/deep 5개 차원. |
| `dimension_verdicts` | Binary 전용 mapping | 차원별 PASS/FAIL. |
| `best_practice_subcriteria` | mapping | 투표된 6개 값으로 모범 사례 차원을 계산. |
| `business_impact_subcriteria` | mapping | 투표된 5개 값. 관측 효과와 추론은 근거·이유에서 구분. |
| `semantic_checks` | array | index, 투표 점수, weight. |
| `semantic_score` | number | 별도 가중 진단 점수. 필수 검사 실패는 여전히 통과를 막는다. |
| `checks` | object | 필수 문구 발견·누락, 금지 문구, 산출물 누락, 라우팅 실패. |
| `judge_rounds` | array | 인용을 포함한 검증된 독립 채점 원문 전부. |
| `metadata` | object | 보존된 정규화 실행 metadata. |
| `judge_cost_usd`, `judge_cost_allocation` | 선택적 | 확인된 batch 비용을 배분하고 방법을 기록. |
| `evidence` | object | 실행 상대 transcript·산출물 manifest 링크. |
| `error` | 오류 전용 string | 실행 환경 원인. 미채점 오류에 일반 차원 값을 만들지 않는다. |

채점 항목은 `{score, rubric_level, reason, evidence}`이고 의미 검사는 `index`를 추가한다. evidence는 비어 있지 않은 `{path, line_start, line_end, quote}` 배열이다. 검증기는 인용문·줄 범위를 확인하고 경로 탈출·다른 사례를 거부하며 eval_target에 따라 출력 출처를 제한한다. 설명만으로 인용을 대체할 수 없다.

### `manifest.json`

- 식별: `schema_version`, `evaluator_version`, `run_id`, `created_at`, `state`.
- 스킬: `name`, `description`, `installed_path`, `source_path`, 소스 `revision`, 내용 `skill_hash`. 해당하면 상위 plugin 스냅샷 출처도 보존한다.
- 입력: 전체 동작 `analysis`, `criteria_hash`, `criteria_backup`, 확정 `options`, `options_hash`, `behavior_hash`, `evaluator_hash`.
- 실행: 의존성·버전 확인, `execution_adapter`, 어댑터 `config`, `config_hash`, 선택적 `msl_fallback_reason`.
- 사용량: `pricing_configuration`과 작성자 사용량. 요청 모델과 실제 실행 모델은 별개 사실이다.
- 체크포인트: ID별 `cases`, 상태 `pending`/`executed`/`graded`/`error`, 실패 정보. 채점 체크포인트는 검증된 사례 ID와 원시 라운드 사용량을 보존한다.
- 발행: 요청한 각 목적지의 상태·영수증 또는 오류. 미요청 쓰기도 명시한다. 평가가 끝났어도 발행 오류가 있을 수 있으므로 발행 상태와 CLI 종료 상태를 확인한다.
- 명세 차이: 정수 배분, 미가용 내부 연동 등 요청 계약과 다른 부분.

CLI 옵션은 한 번 확정한다. 재개는 불변 해시를 검증하고 revision 혼합을 거부한다. 채점 중 중단되었으면 성공한 대상 실행을 반복하지 않고 다시 채점할 수 있다. 기준 변경은 새 실행이 필요하며 manifest를 고쳐 검사를 무력화하지 않는다.

### `summary.json`

- 식별·모드: `schema_version`, `run_id`, `mode`, `grading`.
- 결과: `total`, `passed`, `failed`, `errors`, 사례 `pass_rate`, 채점 사례 평균 `score`, 전체 `verdict`, 선택적 Likert `grade`, `score_distribution`.
- 세부: count/pass_rate를 담은 `categories`, `dimensions`, 6개 `best_practice_subcriteria`. Binary 집계 차원은 통과율이며 단일 사례 판정이 아니다.
- 사용량: `duration_seconds`는 사례별 시간 합, `tokens`는 확인된 입력/출력/cache 합계, `execution_cost_usd`, `judge_cost_usd`, `cost_usd`, `known_cost_subtotal_usd`. 작성 비용은 `author_cost_usd`로 따로 두고 cost_usd에도 포함한다. `execution_and_judge_cost_usd`는 실행·채점 소계다. `wall_clock_seconds`는 재개 중 대기를 포함한 실행·채점 경과 시간이다.
- 진단: `failure_clusters`, case_id별 개선안, 전체 정규화 `results`.

전체 verdict는 모든 사례 통과를 요구한다. 사례별 Likert 3.0/Binary 차원 임계값, 평균 등급과 다르다. Null 합계를 0으로 바꾸지 않는다. 시간·토큰 합계에서 작성·채점이 빠졌으면 범위를 명시한다. Dashboard 비교는 기준·모델·환경 차이를 보존하고 다른 조건을 인과적 개선 실측처럼 표현하지 않는다.

Native staging은 항상 `--eval-dir skill-evaluator-cases --case TC-ID`로 하나를 선택하고 반환 이름도 정확히 한 개인지 확인한다. 상위 plugin에 자체 experimental.evals가 있어도 마찬가지다. 상위 plugin 이름, 형제 scripts/assets, 선언한 의존성을 스냅샷으로 보존하고 전체 plugin hash를 재개 검증에 포함한다.

채점·재사용·보고서 렌더링 전에 보존된 response/transcript/metadata/artifact/evaluation 해시를 검증한다. 근거 누락·변경 시 재사용을 거부하고 기존 점수를 둔 채 조용히 다시 실행하지 않는다.
