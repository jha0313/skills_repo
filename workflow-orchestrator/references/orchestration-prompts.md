# Orchestration prompts

Use only the section relevant to the current handoff or failure. These prompts refine the existing workflow; they do not require extra workers, a new state service, fixed polling intervals or another approval at every stage. Adapt the Korean examples to the user's latest language and the host's actual capabilities.

## Selective context

A worker may not receive the coordinator's previous conversation. Even when history is inherited, identify the current contract so old decisions do not silently win. Include the task's goal, changed decisions, relevant constraints, owned scope and source paths. Label facts versus assumptions. Do not omit raw evidence needed for independent work, or paste every earlier message by default.

```text
이전 대화를 알고 있다고 가정하지 않고 필요한 맥락을 전달합니다.
현재 목표: [이번 작업으로 사용자가 얻을 결과]
적용할 결정·제약: [최신 결정, 사용자 언어, 범위, 승인된 행동]
담당 작업과 완료 조건: [이 worker의 범위와 관찰 가능한 성공 조건]
확인된 사실 / 아직 가설인 것: [구분해서 기록]
필수 원문: [현재 revision, 관련 파일·문서·근거 경로]
불필요한 전체 조사는 반복하지 말고 이 작업에 필요한 원문을 확인하세요.
돌려줄 내용은 결정·변경·근거·남은 의존성 중심으로 요약하세요.
```

This is a way to fill the existing worker brief, not a second mandatory template. Keep bulky evidence at its source and pass a precise pointer instead of stripping away provenance.

## Independent verification

Give the verifier the request, success conditions, actual changes and relevant raw evidence. Include useful design context and known failures, but separate these from the implementer's interpretation. Do not supply an expected PASS or ask it merely to confirm the implementer's conclusion. Respect the authorized side-effect limits.

```text
요구사항과 실제 변경, 원시 실행 근거를 기준으로 독립 검증하세요.
구현자의 성공 판정은 결론으로 받아들이지 마세요.
핵심 주장이 틀렸다면 드러날 관찰이나 반례를 하나 선택해 확인하세요.
직접 확인한 사실, 다른 worker에게 전달받은 주장, 아직 미검증인 항목을 구분하세요.
실행 권한이나 도구가 없으면 그 한계를 보고하고 통과로 바꾸지 마세요.
```

When reports disagree, first identify whether they checked different inputs, revisions, environments or success conditions. Ask the existing appropriate worker for the smallest observation that distinguishes the competing explanations. Do not default to adding more judges or taking a majority vote.

```text
두 보고서의 결론이 다릅니다. [주장 A / 주장 B]
서로 다른 전제와 아직 없는 근거를 짚고, 두 설명을 구별할 가장 작은 검사를 제안하세요.
이미 승인된 범위에서 실행할 수 있으면 그 검사만 수행하세요.
어느 결론을 지지하거나 반박하는지 원시 근거와 함께 돌려주세요.
확인 전에는 두 주장을 합쳐 하나의 확정 결론을 만들지 마세요.
```

## Evidence-backed status

Use the host's existing events and the current task table. Host capabilities vary: an ID may arrive at dispatch, during execution or only on completion. Do not invent an ID or an acknowledgment when none is available.

| State | Evidence that supports it |
|---|---|
| Assigned | The task was sent to an identified worker or accepted by the host. This alone does not prove execution. |
| Executing | The host reports that execution has started, or a worker returns evidence of actual work. |
| Blocked | A concrete unmet dependency or permission/tool limitation, with the next needed action. Silence alone does not establish the cause. |
| Execution-complete | The worker returns its deliverable and execution outcome. Required independent verification may still be pending. |
| Verified | The required success checks have supporting observations for the applicable revision and environment. Unchecked conditions remain explicit. |

If dispatch, receipt or progress is unobservable, say “sent; receipt/progress unconfirmed” rather than upgrading the state. A pane, process or timer being alive is not a meaningful work checkpoint.

```text
진행 상황은 완료된 단계와 확인 가능한 근거로 보고하세요.
호스트가 제공하는 worker/job ID, 최신 의미 있는 결과, 남은 의존성과 다음 행동을 알려주세요.
지시를 받았다는 응답과 실제 실행 결과를 구분하세요.
막혔다면 기다리는 대상과 이미 시도한 접근을 짧게 보고하세요.
```

Choose checkpoints at useful task boundaries, such as a resolved contract, a reproduction, a completed diff or a finished check. Use existing completion events or bounded host waits. If a checkpoint stops advancing, request a concise reconciliation and apply the entrypoint's existing retry/reassignment rule; do not start a perpetual polling loop or another worker doing the same job.

## Steering and resume

Treat the latest user instruction as a change to the affected task contract, including language, scope, authorization and success conditions. Forward the changed part with enough context to identify the task and when the change applies. Keep unaffected work running.

```text
이 작업의 최신 조건이 바뀌었습니다.
변경: [이전 조건 → 새 조건, 적용할 작업]
유지: [바뀌지 않은 목표·범위·승인]
수신했는지와, 현재 진행 중인 작업에 어디까지 반영했는지를 구분해 알려주세요.
새 조건과 충돌하는 작업만 중지하거나 수정하고 부분 결과는 보존하세요.
이전 조건에서의 검증이 여전히 유효한지도 표시하세요.
```

“Sent” means the host accepted a delivery request. “Acknowledged” requires an actual receipt response/event. “Applied” requires a changed plan, action or artifact consistent with the new instruction. Some hosts provide no separate acknowledgment; keep that state unconfirmed without inventing another user approval requirement. If a running tool cannot be interrupted, report the boundary and do not dispatch a duplicate or conflicting operation to compensate.

On resume, use available host state and a worker's reconciliation to locate the previous owner, live commands and existing output. Follow up with that owner when possible. If it is gone, reassign only the unfinished work with the preserved evidence. A conversation restart is not permission to rerun a generation, migration, publication, merge or other operation whose outcome is unresolved.

```text
이전 작업을 새로 시작하지 말고 먼저 재개 상태를 확인하세요.
현재 owner/job, 살아 있는 명령, 현재 revision과 dirty 상태, 이미 만들어진 산출물을 대조하세요.
유효하게 완료된 결과는 재사용하고 미완료 범위만 제시하세요.
실행 중이거나 결과가 불명확한 변경 작업을 중복 수행하지 마세요.
호스트에서 확인할 수 없는 상태는 추측하지 말고 필요한 확인을 알려주세요.
```

## Completion evidence

Before the coordinator reports completion, ask the responsible worker or verifier to reconcile the success conditions against the delivered state. A report can be concise: use the existing task/report artifact instead of creating a new ledger.

```text
최종 성공 조건을 실제 결과와 하나씩 대조하세요.
각 조건: [요청한 결과] → [실제 산출물] → [검증 revision·환경] → [관찰 결과와 근거]
개별 worker의 PASS를 합쳐 전체 성공이라고 판단하지 마세요.
통합 또는 조건 변경으로 무효가 된 검사만 다시 수행하고, 유효한 검사는 반복하지 마세요.
빠진 조건은 미검증으로 남기고 완료를 막는 항목인지 구분하세요.
최종 전달 위치와 반영 상태도 사용자가 요청한 범위와 맞는지 확인하세요.
```

For code, the evidence must apply to the integrated revision being delivered. For a rendered artifact, it must apply to the actual output and relevant viewing environment. For publication, a local file or feature-branch push does not establish the requested remote destination. Use only the delivery scope already authorized; this check does not create merge or deployment authority.
