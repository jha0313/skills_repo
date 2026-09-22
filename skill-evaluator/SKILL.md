---
name: skill-evaluator
description: 설치된 Claude Code 스킬을 처음부터 끝까지 평가한다. 스킬 자체의 계약에서 테스트 사례를 생성하고, 격리 세션에서 실행하고, 기록된 근거를 독립 채점자가 채점해 사례별 PASS/FAIL을 인용 근거와 함께 보고한다. 스킬 품질, 호출 정확성, 회귀, 스킬 변경 전후 비교를 요청할 때 사용한다.
argument-hint: "[skill-name]"
allowed-tools: Read Write Edit Glob Grep Bash Skill AskUserQuestion Agent
metadata:
  version: "1.1.0"
  dependencies:
    runtime: "Python >=3.11, uv, native plugin eval을 지원하는 인증된 Claude Code"
---

# 스킬 평가

지정한 설치 스킬을 평가한다. 모든 것이 로컬에서 실행된다. native `claude plugin eval` sandbox에서 실제 Claude 세션을 실행한 뒤, 별도 채점 세션이 기록된 근거를 줄 단위로 인용해야 한다. 비용은 실제 모델 사용량이다(quick 실행은 약 $3, 에이전트를 띄우는 스킬의 전체 실행은 $10~30).

## 세 단계

1. **환경을 한 번 확인한다:** `uv run <this-skill>/scripts/evaluate.py doctor`. CLI 버전과 native eval 사용 가능 여부를 보고한다. 빠진 것이 있으면 출력된 안내를 따른다.
2. **실행한다:** `uv run <this-skill>/scripts/evaluate.py TARGET --yes`. TARGET은 스킬 이름 또는 `SKILL.md`가 있는 디렉터리다. `--yes`가 없으면 명령은 테스트 사례를 생성한 뒤 멈추므로 사용자가 출력된 표를 검토하고 `<skill>/evals/eval_criteria.yaml`을 편집할 수 있다. `--yes`는 생성된 사례를 그대로 승인하고 대상 스킬의 코드가 sandbox에서 실행되는 것을 신뢰한다는 뜻이다. 스킬의 실제 작업에 그 도구가 필요할 때만 `--allow-tool Write`(그리고 `Edit`, `Bash`, `Agent`)를 추가한다.
3. **결과를 읽는다:** 터미널에 사례별 PASS/FAIL과 한 줄 이유, 이어서 보고서 경로가 출력된다. `--open`은 `REPORT.html`을 연다. 채점자가 인용한 모든 것은 `~/skill-eval/<skill>/<run-id>/` 아래에 있다.

## 크기 선택

- `--quick`: 표준 사례 4개, 채점 세션 1회, 약 5분. 스킬을 고쳐 가며 반복할 때 쓴다.
- 기본: 호출 정확성·효율·모범 사례·업무 효과·과제 완수에 걸친 사례 10개, 사례마다 채점 세션 1회.
- `--rigorous`: 같은 사례 10개를 독립 채점 세션 3개가 채점(중앙값). 스킬 변경 전후 비교에 쓴다.
- `--deep`: 사례 30개.

호출 사례는 스킬 이름을 말하지 않는 자연스러운 요청을 쓰므로 실제 라우팅이 검사된다. 과제 완수 사례는 성공 주장이 아니라 실제 파일과 해시를 확인한다. 사례는 점수와 무관하게 critical 검사 하나라도 실패하면 실패이며, 전체는 모든 사례가 통과할 때만 통과한다.

## 전후 비교

같은 기준을 `--rigorous`로 두 번 실행한 뒤(그 사이에 스킬을 수정하고, 검토한 사례를 재사용하려면 `--criteria <file>`을 넘긴다) `evaluate.py compare RUN_A RUN_B --output compare.html`을 실행한다. 기준이나 evaluator가 다른 실행은 비교를 거부한다. `--resume RUN_DIR`은 중단된 실행을 이어 가고, `--regrade RUN_DIR`은 이전 실행의 보존된 실행 결과를 현재 evaluator로 다시 채점한다.

## 사용자에게 알릴 것

판정과 실패한 사례의 이유를 먼저 말하고, 보고서를 링크하고, 스킬의 약점과 환경 오류를 구분한다(ERROR로 표시된 사례는 채점되지 않은 것이다). 채점 점수를 업무 성과로 제시하지 않는다. 사례 스키마, 채점 루브릭, 결과 파일의 세부는 [references/](references/)에 있다.
