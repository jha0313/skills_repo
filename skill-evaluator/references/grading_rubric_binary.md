# Binary 채점

**PASS/FAIL**을 사용하고 값은 1/0으로 저장한다. Binary 판정 화면에 Likert 숫자나 문자 등급을 표시하지 않는다. 차원별 점수는 이진 값이며 집계 평균은 통과율이라고 명시한다. 원시 rubric_level은 0 또는 1이고 모든 판정은 직접 근거를 인용한다. JSON dimensions는 분석용 숫자를 유지하고 표시용 dimension_verdicts도 포함한다.

호출·효율·완수 차원은 명시된 관찰 조건을 충족해야 통과한다. 모범 사례는 **6개 중 4개**(context_management, subagent_architecture, tool_selection, skill_design, process_adherence, error_handling_safety), 업무 효과는 **5개 중 3개**(time_saved, scale_potential, quality_ceiling, problem_difficulty, productivity_revenue_link)가 통과해야 한다. 적용 가능성을 판단하고 매출·절감 시간을 지어내지 않는다. 단순 작업은 subagent가 없어도 구성 기준을 통과할 수 있다.

BASIC은 **4개 차원 중 3개**, THOROUGH/deep은 **5개 중 4개**가 통과해야 한다. 종합 점수는 통과 차원 수/평가 차원 수, 즉 차원 통과율이다. critical 검사는 모두 통과해야 하며 필수 문구 누락, 금지 문구, 산출물 누락, 잘못된 호출은 종합 값과 무관하게 실패다.

의미 검사 점수 = sum(weight × 0 또는 1)/sum(weights). 각 rubric은 정확히 0과 1을 가진다. 모든 critical 의미 검사가 통과해야 한다. 독립 3라운드가 같은 근거를 채점하고 개별 이진 기준마다 다수결한다. 모범 사례·업무 효과의 하위 기준 임계값은 투표 후 적용한다. 범주 문자열을 평균 내지 않는다.

해당 사례의 응답·도구·산출물 원문을 줄 번호와 함께 정확히 인용한다. 프롬프트, 로드된 스킬 지침, 평가 기준, 다른 사례는 근거가 아니다. 없거나 빈 기록은 score null인 ERROR다. 일반 실패에는 문자 등급 대신 FAIL을 쓴다. 시간 초과 전 실질 작업은 timeout metadata와 함께 채점할 수 있다. 필수 산출물이 없으면 성공 주장과 무관하게 실패한다. 환경 ERROR와 실제 FAIL은 다르며 실제 실패로 잘못된 fallback을 유발하지 않는다.

HTML/Markdown은 판정 배지, 차원별 PASS/FAIL, 통과율, 근거 링크를 사용한다. 모르는 비용·토큰은 미확인으로 남긴다. 독립 채점 원문을 모두 보존한다. 다수결은 안정성을 위한 수단이며 정답 자체가 아니다.

## 서로 다른 통과율

한 사례의 `score`는 선택한 차원 중 통과 비율이다. `semantic_score`는 의미 검사의 가중 통과 비율이며 진단용이다. 필수 의미 검사는 `critical: true`로 표시해 실패가 사례 통과를 막게 한다. 전체 `pass_rate`는 최종 판정이 PASS인 **사례**의 비율이며 ERROR도 분모에 포함한다. 이름을 구분해 표시한다.

전체 `verdict`는 모든 사례 PASS를 요구한다. 사례별 BASIC 3/4, THOROUGH 4/5 임계값을 바꾸는 것은 아니다. 집계 차원 값이 0~1 사이면 여러 사례의 통과율이며 개별 판정이 비이진 값이라는 뜻이 아니다. 원래 채점 결정을 보존하고 다수결 뒤 4/6·3/5 기준을 적용한다.
