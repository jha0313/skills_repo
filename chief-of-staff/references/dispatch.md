# 작업자 띄우기, 이어 시키기, 치우기

`<스킬>`은 이 스킬 폴더, `<상태>`는 상태 폴더의 절대 경로다. 아래 경로는 실제 값으로 채운다.

## 첫 줄 (모든 작업자에게 똑같이)

> 너는 작업 `<id>`의 작업자다. 다른 일보다 먼저 `<스킬>/references/worker.md`와 `<상태>/tasks/<id>/brief.md`를 읽고 그대로 한다. 결과는 `<상태>/tasks/<id>/result.md`에 쓰고 같은 블록으로 끝낸다.

brief에 있는 내용을 이 지시에 다시 쓰지 않는다. 두 곳이 어긋나면 작업자가 고르게 된다.

## 작업 공간

| 종류 | 작업 공간 |
|---|---|
| ship | 격리된 worktree. 호스트가 subagent에 worktree 격리를 주면 그것을 쓰고, 아니면 `git -C <프로젝트> worktree add <상태>/worktrees/<id> -b chief/<id> <기준 브랜치>` |
| run | 사용자의 체크아웃 그대로. 같은 체크아웃에서는 한 번에 하나 |
| scout | 사용자의 체크아웃을 읽기만. 실행이 필요하면 `git -C <프로젝트> worktree add --detach <상태>/worktrees/<id> <기준 브랜치>` |

- worktree에는 git이 추적하지 않는 파일(`.env`, 설치된 패키지)이 없다. `projects.md`의 setup을 brief 지시의 첫 줄에 옮긴다. 비밀 파일은 복사하지 않는다. 필요하면 `needs-human`이다.
- worktree는 파일만 나눈다. 포트, 데이터베이스, 외부 계정은 공유된다. 부딪칠 작업은 차례로 한다.

## 띄우는 방법

1. `HERDR_ENV=1`이면 herdr 새 탭의 세션(Claude 또는 Codex). 사용자가 볼 수 있어 먼저 쓴다. 공급자·모델·effort는 [routing.md](routing.md)의 `route.py`가 정한다. 아래 `<route.py가 낸 인자>` 자리에 그 출력의 `띄울 때 붙일 인자`를 그대로 한 번 넣는다. 명령은 설치된 `herdr --help`, `herdr tab`, `herdr agent`가 기준이다. `<herdr 작업 공간>`은 그 프로젝트의 것, 없으면 `$HERDR_WORKSPACE_ID`다. pane id는 `tab create`가 준 `.result.root_pane.pane_id`다. `<이름>`은 소문자로 시작하는 32자 안의 작업 id다.

   ```bash
   herdr tab create --workspace <herdr 작업 공간> --cwd <작업 공간> --label "<프로젝트> · <하는 일>" --no-focus
   herdr agent start <이름> --kind claude --pane <pane id> -- -n "<프로젝트> · <하는 일>" --permission-mode auto <route.py가 낸 인자>
   herdr agent prompt <이름> "<첫 줄>"
   ```

   Codex로 보낼 때는 둘째 줄이 다르다. 인자에 샌드박스와 승인 방식, 쓸 수 있는 폴더가 들어 있다([까닭](routing.md#codex-작업자)). Codex 작업자는 결과 폴더에만 쓸 수 있으니 먼저 그 폴더를 만들고, 첫 줄의 결과 자리를 `<상태>/tasks/<id>/out/result.md`로 바꿔 보낸다.

   ```bash
   mkdir -p <상태>/tasks/<id>/out
   herdr agent start <이름> --kind codex --pane <pane id> -- <route.py가 낸 인자>
   ```

   끝나면 `out` 안의 `result.md`(scout는 `report.md`도)를 `<상태>/tasks/<id>/`로 옮긴다. 옮기기 전에는 보고판에 결과가 없다.

   권한 확인은 끄지 않는다. 신뢰나 허용 창이 떠 `agent_not_ready`·`agent_blocked`가 나오면 대신 누르지 않고 사용자에게 어느 탭인지 알린다. `herdr agent get <이름>`의 상태는 참고일 뿐, 결과는 `result.md`다.
2. herdr가 없으면 호스트의 subagent(백그라운드가 되면 백그라운드). 이름에 작업 id를 넣고, 호스트가 받으면 모델과 effort를 같은 값으로 준다. Codex로 갈 일은 3번으로 한다.
3. subagent도 없으면 사용자에게 작업 공간 경로와 첫 줄을 주고 새 세션에 붙여 넣게 한다. 그 세션도 권한 확인은 켠 채로 쓴다. Codex로 갈 일이면 결과 폴더를 만들어 두고, 실행할 폴더(작업 공간. 인자에 `-C`가 든 scout만 어디서든 된다)와 `codex <route.py가 낸 인자>` 전체 명령을 함께 준다. 인자 없이 열면 쓰기 범위가 풀린다.

**띄우기 전에** `route.py`가 `보낼 곳: 없음`이나 `띄워도 되나: 아니오`를 내면 띄우지 않는다. 여럿을 띄울 때도 하나씩 띄우고 그때마다 다시 잰다. brief의 `model`에 정한 값을, `worker`에 어디 있는지 적는다(herdr는 세션 이름·탭 id·pane id, subagent는 이름). 보고판의 `작업 중`에 그대로 나온다.

작업자가 상태 폴더에 쓸 권한이 없으면 마지막 메시지의 블록을 글자 그대로 `result.md`에 저장한다.

## 결과를 받으면

| RESULT | 행동 |
|---|---|
| `done` | SKILL.md 5단계 |
| `needs-decision` | 근거, 영향, 선택지, 추천 순으로 묻는다. 머지·게시·삭제·발송이면 SKILL.md 6단계대로 승인을 받는다. 답을 적고 그 작업자에게 이어 시킨다 |
| `needs-human` | 보고 맨 위에 무엇을 어디서 할지. 했다고 하면 이어 시킨다 |
| `blocked`·`failed` | 정보나 지시로 풀 수 있으면 이어 시키고, 아니면 막힌 곳을 근거와 함께 알린다. 승인받은 행동이 실패했으면 이어 시키지 않고 다시 묻는다 |
| 없음·깨짐 | 작업 공간을 보고 result를 다시 쓰게 한다 |

## 이어 시키기

다른 모델이나 공급자로 옮겨 이을 거면 아래를 하기 전에 [옮기기](routing.md#도는-작업자-옮기기)의 조건을 먼저 본다. 맞지 않으면 옮기지 않고 같은 작업자에게 잇는다.

1. 받은 답이나 추가 요청의 원문을 brief의 `결정 기록`에 덧붙인다(비밀값은 `[가림]`). 승인받은 행동은 brief의 `승인받은 행동`에 적고, 이미 실행했거나 다시 묻는 줄은 `결과:`를 채워 작업자가 다시 하지 않게 한다. push와 PR 만들기는(나중에 승인받았어도 같다) 비서실장은 하지 않고, 사용자가 말한 문장을 brief의 `지시`에 적어 그 ship 작업자가 하게 한다.
2. 지난 `result.md`를 `result-1.md`처럼 번호를 붙여 옮긴다. 그대로 두면 지난 라운드의 결과로 판정한다.
3. brief의 `ask`와 `checked`를 비운다.
4. 옮기지 않으면 살아 있는 작업자에게 "brief의 결정 기록 마지막 줄과 승인받은 행동을 읽고 이어서 한다"를 보낸다. 없거나 옮기기로 했으면 같은 작업 공간에 새 작업자를 첫 줄로 띄우고, 먼저 `git status`와 `git diff`로 남은 상태를 보게 한다. 승인받은 행동이나 push·PR을 맡긴 작업이면 이미 됐는지 밖의 결과부터 보게 한다.

같은 지시는 두 번까지만 보낸다(승인받은 행동은 한 번). 세 번째는 범위를 줄이거나 방법을 바꾸거나 사용자에게 묻는다.

## 치우기

닫힌 작업의 폴더는 기록이므로 그대로 둔다. worktree와 브랜치를 지우는 것은 삭제 승인이 필요하다. 묻기 전에 `git -C <작업 공간> status --short`와 기준 브랜치에 없는 커밋(`git log --oneline <기준>..HEAD`)을 보여 준다. 승인은 SKILL.md 6단계를 따르고, 지우는 것은 그 작업 공간 밖에서 뜬 작업자가 한다. 지울 때는 `--force`와 `-D` 없이 지워지는 것만 지운다. 남은 변경 때문에 거부되면 그 사실을 알리고 다시 묻는다. squash 머지 뒤에는 `git branch -d`가 거부될 수 있다. PR의 `state`가 `MERGED`인지 보여 주고 다시 묻는다.
