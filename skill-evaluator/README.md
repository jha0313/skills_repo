# skill-evaluator

동료의 작업을 검토하듯 Claude Code 스킬을 평가한다. 실제 과제를 주고, 실제로 무엇을 하는지 지켜보고, 독립 채점자가 기록된 근거를 채점하게 한다. 모든 것이 Claude Code의 native `claude plugin eval` sandbox 위에서 로컬로 실행된다.

## 설치

`SKILL.md`는 scripts와 references를 사용하므로 `skill-evaluator/` 전체를 함께 둔다. 평소의 Claude Code 스킬 설치 방식을 사용하거나 디렉터리를 `~/.claude/skills/skill-evaluator`로 복사한다. 아래 명령은 [jha0313/skills_repo](https://github.com/jha0313/skills_repo) checkout에서도 실행할 수 있다.

필수 환경: Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/), native eval을 사용할 수 있는 인증된 Claude Code. 한 번 확인한다.

```bash
uv run skill-evaluator/scripts/evaluate.py doctor
```

## 사용

```bash
# 사례 4개, 채점 1회, 약 5분 — 스킬을 고쳐 가며 반복할 때
uv run skill-evaluator/scripts/evaluate.py my-skill --yes --quick

# 사례 10개, 사례마다 채점 1회 — 기본
uv run skill-evaluator/scripts/evaluate.py my-skill --yes

# 사례 10개, 사례마다 채점 세션 3회(중앙값) — 전후 비교용
uv run skill-evaluator/scripts/evaluate.py my-skill --yes --rigorous --allow-tool Write
```

`my-skill`은 설치된 스킬 이름 또는 `SKILL.md`가 있는 디렉터리다. 실행은 생성된 사례의 검토 표를 출력하고, 실행하고, 채점한 뒤 사례별 한 줄로 끝난다.

```text
FAIL: 9/10 cases passed, grade B, ~$28.85 (CLI estimate), 43 min
  TC-001  PASS  4.67  Natural routing for a read-only delegation
  ...
  TC-010  FAIL  3.33  Resume with an unverified PASS claim
                          protected file changed: STATE.md
Report: ~/skill-eval/my-skill/<run-id>/REPORT.md  (HTML: .../REPORT.html)
```

`--yes`는 생성된 사례를 승인하고 대상 스킬의 코드가 sandbox에서 실행돼도 된다고 확인하는 것이다. 빼면 표를 출력한 뒤 멈추므로 `<skill>/evals/eval_criteria.yaml`을 편집하고 `--criteria <that file> --yes`로 다시 실행한다. 스킬의 실제 작업에 Read, Glob, Grep, Skill 외의 도구가 필요하면 도구마다 `--allow-tool`을 추가한다. `--open`은 HTML 보고서를 연다. 종료 코드 0은 전체 통과, 1은 사례 실패, 2는 환경 오류로 채점되지 않은 사례가 있음, 130은 중단(`--resume RUN_DIR`로 이어 간다)이다.

## 실행이 하는 일

1. **분석.** 스킬 자체의 파일을 분석해 스킬이 약속한 것을 검사하는 사례 10개(`--quick`은 4개, `--deep`은 30개)를 작성한다. 자연어 호출 사례 2개(호출돼야 하는 것 하나, 호출되지 않아야 하는 것 하나), 효율 사례 1개, 모범 사례 2개, 업무 효과 사례 2개, 실제 파일을 쓰는 과제 완수 사례 3개다. 기존 기준은 덮어쓰기 전에 백업한다.
2. **실행.** 각 사례를 스킬 사본과 fixture 파일이 든 깨끗한 native sandbox에서 실행한다. 실행 기록, 최종 응답, 모든 도구 호출(누가 호출했는지, 즉 세션 자신인지 위임된 작업자인지 포함), 생성된 파일과 해시를 저장한다.
3. **채점.** 별도 채점 세션에서 채점한다. 채점 세션은 기록된 근거만 보고 프롬프트나 스킬 본문은 보지 못한다. 모든 점수는 파일과 줄을 인용해야 한다. 인용은 검증되며, 인용이 맞지 않는 라운드는 버리고 한 번 다시 시도한다. 3라운드(`--rigorous`)는 중앙값으로 합친다.
4. **보고.** `REPORT.md`, `REPORT.html`, `summary.json`과 사례별 평가 파일 하나를 작성하며 모두 근거에 연결된다.

사례는 종합 점수와 무관하게 critical 검사(필수 파일 누락, 보호 파일 변경, critical 루브릭 질문 3/5 미만, 잘못된 라우팅) 하나라도 실패하면 실패다. 전체는 모든 사례가 통과할 때만 통과한다.

## 옵션

| 옵션 | 동작 |
|---|---|
| `--quick` | 사례 4개, 채점 세션 1회, 동시 실행 4 |
| `--rigorous` | 사례마다 채점 세션 3회 |
| `--deep` | 사례 30개 |
| `--binary` | 1~5 대신 PASS/FAIL 루브릭 |
| `--yes` | 생성된 기준을 승인하고 대상을 신뢰 |
| `--criteria FILE` | 검토했거나 직접 쓴 기준으로 실행 |
| `--allow-tool T` | 평가 대상 세션에 허용할 추가 도구(반복 가능) |
| `--model`, `--judge-model` | 평가 대상·채점 모델 고정. 없으면 CLI 기본값을 쓰고 기록한다 |
| `--concurrency N` | 동시 실행 사례 수(1~8, 기본 3). 사례마다 자체 sandbox를 쓴다. 공유 외부 자원을 건드리는 스킬은 `--sequential`로 한 번에 하나씩 실행한다 |
| `--timeout`, `--judge-timeout` | 평가 대상 세션 / 채점 세션별 초 단위 제한 |
| `--open` | 끝나면 `REPORT.html`을 연다 |
| `--resume RUN_DIR` | 저장된 옵션으로 중단된 실행을 이어 간다 |
| `--regrade RUN_DIR` | 실행의 보존된 실행 결과를 현재 evaluator로 채점한다 |
| `compare RUN_A RUN_B --output FILE.html` | 기준이 같은 두 실행의 전후 비교 dashboard |

## 전후 비교

스킬을 `--rigorous`로 실행하고, 수정하고, 같은 `--criteria` 파일로 다시 실행한 뒤 `compare`한다. 기준이나 evaluator 해시가 다른 실행은 비교를 거부한다. 비교는 관찰 결과다. 같은 기준·모델·fixture라야 PASS/FAIL 변화를 해석할 수 있고, 소수 둘째 자리 수준의 종합 점수 차이는 채점 변동 범위 안이다.

## 한계

채점자는 모델이다. 3라운드 합의는 변동을 줄이지만 공통 편향은 없애지 못한다. 같은 스킬도 다시 실행하면 점수가 달라질 수 있다. 업무 효과는 루브릭 판단이며 실측 결과가 아니다. 비텍스트 산출물(이미지, PDF)은 도메인 렌더러 없이 채점하지 않는다. 표시된 비용은 CLI 정가 추정치이며 청구서가 아니다. sandbox가 임의의 plugin을 변경 없이 실행한다고 보장할 수 없다. 의존성이 빠지면 점수를 지어내지 않고 오류를 낸다.

사례 스키마·mock은 [references/test_case_format.md](references/test_case_format.md), 루브릭은 [grading_rubric.md](references/grading_rubric.md), 실행이 남기는 파일은 [result_schema.md](references/result_schema.md), 보고서 계약은 [report_template.md](references/report_template.md)를 참고한다.
