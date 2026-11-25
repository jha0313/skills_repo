# chief-of-staff

여러 프로젝트를 **비서실장 세션 하나**에 맡기는 작은 스킬이다. 나는 비서실장하고만 이야기하고, 비서실장은 관리만 한다. 실제 일은 승인받은 머지나 삭제까지 작업자(herdr 새 탭의 세션, subagent, 새 세션)가 한다. 우선순위·결정·결과는 대화가 아니라 디스크에 남아서, 세션이 바뀌어도 "오늘 뭐 봐야 해?"에 답한다.

```text
나 ── 비서실장 ─┬─ ship  작업자: 격리된 작업 공간 → 커밋·PR
                ├─ run   작업자: 내 체크아웃에서 실행 → 산출물
                └─ scout 작업자: 읽기 전용 조사 → 보고서
      ~/.chief-of-staff/  focus · decisions · projects · tasks/<id>/{brief,result}
```

## 언제

- 프로젝트 여러 개를 동시에 굴리고, 무엇을 먼저 봐야 할지 한곳에서 알고 싶을 때.
- 머지·게시·삭제·발송 전에 무엇이 어디로 나가는지 보고, 내 답이 원문으로 남기를 바랄 때.

한 작업을 처음부터 끝까지 맡기려면 [workflow-orchestrator](../workflow-orchestrator/README.md)가 맞다. 비서실장은 그 위에서 **여러 작업**의 순서, 승인, 보고를 맡는다. 큰 ship 작업 안에서 workflow-orchestrator를 불러도 된다.

## 설치

```bash
npx skills add jha0313/skills_repo --skill chief-of-staff
```

Python 3.11 이상과 git이 필요하다. PR 작업에는 로그인된 `gh`가 필요하다. herdr 안에서는 작업자를 새 탭의 Claude 세션으로 띄워 눈에 보이게 하고, 없으면 subagent를 쓴다. subagent도 없는 호스트에서는 사용자가 새 세션을 열어 첫 지시를 붙여 넣는다. 상태 폴더는 `CHIEF_OF_STAFF_HOME`으로 바꾼다(기본 `~/.chief-of-staff/`). 호스트에 따라 작업자가 그 폴더에 쓸 때 권한 확인이 뜬다.

## 예시 대화

```text
나        비서실장, 이번 주는 acme-web 결제가 먼저야. 마감 1/20.
비서실장  focus.md에 적었습니다.
나        acme-web 로그인 버그 고쳐서 PR까지. demo-api는 왜 느린지 조사만 해 줘.
비서실장  login-fix(ship), slow-api(scout)를 띄웠습니다.
  …
나        오늘 뭐 봐야 해?
비서실장  1. login-fix: PR을 main에 머지할지 정해 주세요. https://github.com/example/acme-web/pull/12
             head 3f2a9c1, CI 초록, 파일 2개. 되돌리려면 revert PR이 필요합니다.
          2. acme-web 마감 D-2: 결제 화면. 아직 맡긴 작업이 없습니다.
          3. slow-api 조사 끝: 목록 조회마다 쿼리가 41번 나갑니다(재현 로그 확인함).
          나머지: 작업 중 1 · 끝남 3
나        응 머지해
비서실장  답을 기록하고 login-fix 작업자에게 넘겼습니다. 작업자가 head가 그대로인 것을 보고
          한 번 머지했고, 밖에서 MERGED를 확인했습니다.
```

## 보고판

```bash
python3 -I chief-of-staff/scripts/inbox.py          # 읽기 전용, 네트워크 없음
python3 -I chief-of-staff/tests/run_tests.py        # 임시 폴더만 쓴다
```

정렬은 사람 차례(`needs-human`, `needs-decision`, 답을 기다리는 물음) → 7일 안의 마감(지난 것 먼저) → 막힌 것(`blocked`, `failed`, 읽을 수 없는 결과) → `focus.md` 우선순위다. `done`이어도 비서실장이 확인하기 전에는 "확인 전(작업자의 말)"으로 나온다. 확인한 뒤 `result.md`가 바뀌면 지문이 달라져 다시 확인하라고 나온다.

## 못 하는 것

- **강제하지 못한다.** 규칙을 적은 지침이다. 에이전트가 어기면 막을 훅이 없고, 승인 기록은 잘못 적용하는 실수를 줄일 뿐 위조를 막지 못한다. 호스트의 권한 확인과 브랜치 보호를 켜 두고 쓴다.
- 작업자를 지켜보거나 알림을 보내지 않는다. 죽은 작업자는 다음에 보고판을 볼 때 확인한다.
- 보고판은 작업자가 실제로 도는지, PR이 실제로 머지됐는지 모른다. 파일에 적힌 것만 읽는다.
- 여러 컴퓨터나 여러 사람이 상태를 나눠 쓰는 것은 고려하지 않았다. 비서실장 세션은 한 번에 하나만 연다.
- 상태 폴더에 요청과 답의 원문이 평문으로 남는다. 비밀값은 가려 적으라고 지시하지만 자동으로 걸러 주지는 않는다.

## 출처

독립적으로 쓴 스킬이다. 조율자 한 명이 직접 고치지 않고 작업자에게 맡기는 방식과 작업 종류 구분은 workflow-orchestrator에 영감을 준 [firstmate](https://github.com/kunchenguid/firstmate)(MIT)와 개념이 겹칠 수 있다. 문장이나 코드는 가져오지 않았다. 고지는 [THIRD_PARTY_NOTICES](https://github.com/jha0313/skills_repo/blob/main/workflow-orchestrator/THIRD_PARTY_NOTICES.md)에 있다.
