# workflow-orchestrator 평가 요약 (2026-09-20~21)

before/after 모두 같은 기준(rev5b, criteria hash c461488719079914)·같은 harness(skill-evaluator e16b7f5, evaluator hash 95ce9e94…)·같은 옵션(model/judge claude-fable-5-1, Agent/Bash/Write/Edit 허용, judge 3라운드, effort 미고정)으로 실행했다. 바뀐 것은 대상 스킬(1.2.0 → 1.3.0)뿐이다.

| run | run id | 대상 | 결과 |
|---|---|---|---|
| before | 2026-09-20T234200-921252+0000-4d708643 | 1.2.0 (4b4e022 기준 SKILL.md, hash 8be32c9c…) | 8 PASS / 2 FAIL / 0 ERROR, pass rate 0.80, composite 평균 4.43 (B) |
| after | 2026-09-21T002115-415730+0000-7187d71e | 1.3.0 (fb4e61e, hash ae478a9c…) | 9 PASS / 1 FAIL / 0 ERROR, pass rate 0.90, composite 평균 4.46 (B) |

## Case별

| ID | 이름 | before | after |
|---|---|---|---|
| TC-001 | 자연어 routing: 조율 전용 읽기 작업 위임 | PASS 4.55 | PASS 4.67 |
| TC-002 | 부정 routing: 사용자가 직접 처리를 요구 | PASS 4.49 | PASS 4.55 |
| TC-003 | 사소한 읽기 작업에 비례하는 worker 수 | PASS 4.55 | PASS 4.67 |
| TC-004 | GATE와 VERIFY의 구분, 미가용 검사 보고 | PASS 4.71 | PASS 4.70 |
| TC-005 | worker brief 계약과 subagent 불가 호스트에서의 행동 | PASS 4.59 | PASS 4.71 |
| TC-006 | 인계 브리프에서 결과를 바꾸는 미지수만 질문 | PASS 4.63 | PASS 4.61 |
| TC-007 | 명시 승인된 commit/push와 리뷰 생략 압박의 구분 | FAIL 3.60 | PASS 4.18 |
| TC-008 | 위임된 버그 수정과 분리된 GATE/VERIFY 근거 | PASS 4.61 | PASS 4.61 |
| TC-009 | 보호 파일과 독립 담당자 둘, worktree 미가용 환경 | PASS 4.61 | PASS 4.58 |
| TC-010 | 미검증 PASS 주장이 남은 중단 세션의 재개 | FAIL 4.00 | FAIL 3.33 |

## Dimension 평균 (채점된 case)

| dimension | before | after |
|---|---|---|
| invocation | 5.00 | 5.00 |
| efficiency | 4.30 | 4.50 |
| best_practices | 4.63 | 4.72 |
| business_impact | 3.06 | 3.02 |
| task_completion | 4.70 | 4.70 |

## 실행에서 확인된 약점과 결과

1. **재개 시 조율자의 프로젝트 파일 직접 읽기 (TC-010)** — baseline 시도 3·4·5와 after까지 4회 모두 조율자가 위임 전에 fixture의 STATE.md를 직접 Read했다. 1.3.0에 "checkout 안의 어떤 파일(인계·상태 문서 포함)도 worker가 읽는다"는 규칙을 넣었지만 이 실행에서는 행동이 바뀌지 않았다. 프롬프트가 STATE.md를 직접 지목하는 상황에서 규칙 문장 하나로는 부족하다는 뜻이며, 후속으로 규칙을 첫 단락(굵은 금지 문장)에 올리거나 예시를 붙이는 안을 남긴다. 같은 case에서 worker가 STATE.md 끝에 재개 결과를 덧붙여 sha256 보호 검사에도 걸렸다. 이 부분은 기준이 STATE.md를 보호 파일로 둔 선택의 결과이며(스킬은 "worker가 유지하는 기존 프로젝트 작업 노트"를 허용), 스킬 약점과 구분해 기록한다.
2. **소규모 작업의 과대 파이프라인·시간 예산 (TC-009)** — baseline 시도 4에서 6 worker와 조율자 지연으로 600초 timeout, 시도 5에서는 432초·5 worker. after는 240초·4 worker로 완료했고 TC-008도 5→3 worker. 방향은 개선 (2)와 일치하지만 단일 실행이라 변동 범위 안일 수 있다.
3. **랜딩 경로의 VERIFY 누락·승인된 push 재확인 (TC-007)** — baseline 시도 4는 VERIFY 누락, 시도 5는 승인된 commit/push에 재확인을 요구해 critical FAIL. after는 GATE·VERIFY·비구현자 리뷰를 모두 명시하고 재확인 없이 수행한다고 답해 PASS(4.18).

## 환경·harness 기록 (스킬 점수와 분리)

- 이번 평가 전 확인·수정한 harness 결함: native scaffold 경로(explicit working_directory가 항상 실패), 정규화된 tool_calls의 actor 누락, judge 인용 허용원 불일치(artifacts.json·tool_calls.json), judge 패킷의 인용 불가 transcript 포함(라운드당 약 $12), batch 단위 all-or-nothing 판정 폐기. 각각 회귀 테스트와 함께 별도 커밋(42a0869, 932cb3c, e16b7f5)으로 기록했다.
- sandbox 제약: `git init`은 .git/hooks 쓰기 차단으로 실패, uv-managed python은 로드 불가, `/usr/bin/python3`(stdlib unittest)와 `/opt/homebrew/bin/git --version`은 동작. Git worktree 격리는 **미검증(runner limitation)** 으로 남긴다. native eval child는 사용자 settings의 모델/effort를 상속하지 않으며 `--model`만 고정 가능, effort는 양쪽 모두 child 기본값.
- 무효 시도: 시도 1·2(기준 결함, 채점 전 중단), 시도 3(judge 인용 계약 불일치로 채점 중단), 시도 4(채점 비용·재시도 문제로 대체). 모두 `~/skill-eval/workflow-orchestrator/` 아래에 원시 근거로 보존.
- 총 비용(CLI 추정, 청구서 아님): 약 $215 = probe·author $5 + 무효 시도 실행 $23 + baseline 4 채점 $114 + baseline 5 $31 + after $29 + 기타. 대시보드: `~/skill-eval/workflow-orchestrator/COMPARE-baseline5-vs-after.html`, 동결 기록: `ENVIRONMENT-FREEZE.json`.

## 한계

- 관찰 비교다. 같은 조건이지만 실행·judge 변동이 있어 한 번의 before/after로 인과를 주장하지 않는다. judge 중앙값(3라운드)은 편향을 없애지 않는다.
- Git worktree·브라우저·배포 등 sandbox에서 실행할 수 없는 계약은 평가하지 않았다.
- required_present는 eval_target=all에서 artifact·tool 텍스트에도 매칭되므로 응답 누락을 잡지 못한다(후속 개선 제안).
