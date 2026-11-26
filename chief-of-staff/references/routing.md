# 어느 모델로 보내나

작업자를 띄우기 전에 공급자(Claude · Codex), 모델, effort를 정한다. 계산은 스크립트가 하고, 비서실장은 난이도만 고른다. `<스킬>`은 이 스킬 폴더, `<상태>`는 상태 폴더다.

```bash
python3 -I <스킬>/scripts/usage.py --herdr-agent <Claude 세션 이름> > <상태>/usage.json
python3 -I <스킬>/scripts/route.py --kind <ship|run|scout> --level <high|mid|low> --task <id> --workspace <작업 공간> --usage <상태>/usage.json
```

출력의 `brief의 model:` 줄을 brief의 `model`에 적고, `띄울 때 붙일 인자:`를 [dispatch.md](dispatch.md#띄우는-방법)의 명령에서 그 자리에 한 번 넣는다. `이유:` 줄은 brief의 `결정 기록`에 옮긴다. 사용량은 작업자를 띄울 때마다 다시 읽는다. 읽은 지 60분 넘게 지난 `usage.json`은 `route.py`가 받지 않는다. `보낼 곳: 없음`이나 `띄워도 되나: 아니오`면 띄우지 않는다. Codex를 쓰지 않는 호스트에서는 `--without codex`를 붙인다. `띄우는 방식: 호스트의 Claude subagent만`이 나오면 Claude CLI가 없다는 뜻이다. herdr 세션으로 띄우지 않는다.

## 난이도

| level | 어떤 일 |
|---|---|
| `high` | 틀리면 비싼 일. 머지·배포·게시·삭제·돈·보안이 걸린 구현, 설계, 다른 작업자의 결과 검증, 원인을 모르는 버그 |
| `mid` | 범위가 정해진 구현, 정해진 명령으로 산출물 만들기, 재현되는 문제의 진단 |
| `low` | 조사·대조·목록 만들기, 기계적 수정(이름 바꾸기·포맷), 같은 일의 반복 |

둘 사이에서 망설여지면 높은 쪽으로 한다. Claude가 만든 것을 독립으로 봐야 하면 `--other-eyes`, 오늘 안에 끝나야 하면 `--urgent`를 붙인다. `--other-eyes`는 scout와 run에만 쓴다. 리뷰는 고치는 일이 아니다.

## 기본 표

사용량이 보통이거나 모를 때의 값이다. 모델은 별칭으로 적는다. 별칭이 가리키는 판은 호스트가 정한다.

| level | ship | run | scout |
|---|---|---|---|
| `high` | fable high | fable high | fable high |
| `mid` | opus high | opus medium | opus medium |
| `low` | sonnet medium | sonnet medium | sonnet medium |

`--other-eyes`는 level과 상관없이 Codex high다. Codex 모델은 Codex 설정의 기본 모델을 쓴다. 바꾸려면 `<상태>/routing.json`에 `{"codex_model": "<구현용>", "codex_review_model": "<리뷰용>"}`을 둔다. 리뷰도 작업자가 한다. 비서실장이 리뷰 도구를 직접 부르지 않는다.

## 균형

한도 셋(Claude 주간 · Fable 주간 · Codex 주간)마다 쓴 %와 초기화까지 남은 시간으로 상태를 낸다. 속도는 `쓴 % ÷ 창이 열린 뒤 그 값을 본 때까지 지난 시간`이고, 창이 막 열렸을 때 부풀지 않게 지난 시간은 적어도 12시간으로 잡는다. 아래 표에서 위에서부터 처음 맞는 줄이 상태다.

| 상태 | 뜻 |
|---|---|
| 모름 | 읽지 못했다. 초기화 시각이 이미 지난 값이다. 24시간 넘게 묵은 값이다(닿은 값은 초기화 시각이 아직 앞에 있어 같은 창인 것이 확인되면 그대로 쓴다). 보통으로 다룬다 |
| 닿음 | 97% 이상 썼다 |
| 남음(곧 초기화) | 초기화가 6시간 안이라 남은 것이 곧 사라진다 |
| 빠듯 | 이 속도면 초기화 전에 100%에 닿는다. 또는 85% 이상 썼다 |
| 남음 | 이 속도면 초기화 때 70%도 못 쓴다 |
| 보통 | 그 사이 |

`route.py`는 위에서부터 처음 맞는 줄을 따른다.

1. `--other-eyes`이고 Codex를 쓸 수 있으면 Codex. Codex를 못 쓰면 띄우지 않고 사용자에게 묻는다. Claude의 다른 모델이 봐도 되는지 답을 받으면 `--other-eyes` 대신 `--not-model <만든 모델의 별칭>`으로 다시 돌린다.
2. Claude를 못 쓰면(닿음 · 없음) Codex. 둘 다 못 쓰면 띄우지 않는다.
3. `mid`·`low`인데 Claude가 빠듯하고 Codex는 쓸 수 있고 빠듯하지 않으면 Codex. 어려운 일만 Claude에 남긴다.
4. `mid`·`low`인데 Codex를 쓸 수 있고 Codex가 남고 Claude는 남지 않으면 Codex. 한쪽 구독만 남기지 않는다.
5. 나머지는 기본 표. Fable이 빠듯하거나 닿았으면 opus로 내린다. Claude가 빠듯한데 Codex로 못 보내면 `mid`를 sonnet high로 내린다. Claude가 남으면 `mid`·`low`의 effort를 high로 올리고, Fable도 남으면 `mid` ship을 fable medium으로 올린다.

빠듯하면 일이 다른 곳으로 가서 속도가 떨어지고, 속도가 떨어지면 다시 돌아온다. 그래서 한 번의 판정을 오래 쓰지 않는다.

## 사용량을 읽는 곳

`usage.py`는 읽기만 한다. 못 읽은 값은 `null`이고 까닭이 `notes`에 낱말로 남는다. `route.py`는 그것을 모름으로 다룬다.

- **Claude 주간**: 세션 화면의 상태 줄에 `| 5h -- | 7d 42% (3d5h)` 칸이 있으면 읽는다. 상태 줄 스크립트가 Claude Code가 주는 `rate_limits` 값을 그 꼴로 찍어야 한다. 없으면 아래 `/usage` 화면에서 읽는다.
- **Fable 주간**: `/usage` 화면에만 있다. 쉬고 있는 Claude 작업자 세션 하나에 열었다 닫는다. 일하는 세션과 사용자가 직접 쓰는 세션에는 보내지 않는다.

  ```bash
  herdr agent prompt <쉬는 세션> "/usage"
  python3 -I <스킬>/scripts/usage.py --herdr-agent <쉬는 세션> > <상태>/usage.json
  herdr agent read <쉬는 세션> --source visible --lines 200 | grep -A1 -E "^[[:space:]]*Current week \(all models\)[[:space:]]*$" | grep -Eq "[0-9]% used[[:space:]]*$" && herdr agent send-keys <쉬는 세션> Escape
  ```

  화면이 늦게 뜨면 `fable`이 `null`이다. 그때는 둘째 줄을 두 번까지 다시 돌리고, 그래도 없으면 모름으로 둔다. 셋째 줄은 `/usage` 화면의 제목 줄과 그 바로 아래 막대를 함께 본 때만 Escape를 보낸다. 화면이 안 떴는데 보내면 다른 것을 닫는다. 초기화 시각이 이미 지난 화면은 옛 창의 값이라 읽지 않는다.
- **Codex 주간**: Codex 세션 기록에 남은 마지막 주간(7일 창) `rate_limits`. `age_h`가 그 값의 나이다. 본 뒤에 창이 새로 열렸으면 `null`이다(새 창의 값은 본 적이 없다). 다 읽지 못한 기록에 더 새 값이 있을 수 있을 때도 `null`이다. Codex 작업자를 한 번 띄우면 새 값이 생긴다. Codex 세션 화면 아래 줄의 `weekly NN% left`와 맞춰 본다.
- **빈 메모리**: macOS `memory_pressure`, Linux `/proc/meminfo`.

`usage.json`에는 사용량이 들어 있다. 상태 폴더 밖으로 내보내지 않는다.

## 동시에 띄우는 수

수를 정해 두지 않고 빈 메모리로 정한다. `띄워도 되나: 아니오`(빈 메모리 30% 미만)면 띄우지 않는다. 끝난 세션을 닫을지 사용자에게 묻거나 기다린다. 여러 작업을 함께 돌릴 때도 띄우는 것은 하나씩이다. 하나 띄우고 `usage.py`를 다시 돌린 뒤 다음을 띄운다. 메모리가 바닥나면 모든 세션이 함께 끊긴다.

## 리셋권

구독에 따라 한도를 바로 채워 주는 리셋(limit reset)이 가끔 주어진다. 주간 리셋은 주간 한도를, Fable 리셋은 Fable에 쓴 주간 사용량만 채운다. 한 번 쓰면 되돌릴 수 없다(2026-11-25 확인, [About limit resets](https://support.claude.com/en/articles/17007452-about-limit-resets)).

- **사용자만 쓴다.** 웹·데스크톱·모바일의 Settings > Usage에 있고 터미널에는 없다. 비서실장과 작업자는 쓰지 않고, 쓰라고 화면을 조작하지도 않는다.
- `route.py`가 `리셋권: … 사용자에게 묻는다`를 낼 때만 묻는다. 급하고(`--urgent`), 한도에 닿았고, 초기화가 24시간 넘게 남았고, 다른 길이 모자랄 때다. 빈 메모리가 모자라 어차피 못 띄울 때는 묻지 않는다. Fable 리셋권은 `high` 일인데 Fable만 닿았을 때, 주간 리셋권은 Claude 주간에 닿았는데 Codex도 못 쓰거나 `high` 일일 때. Codex로 보내는 독립 리뷰(`--other-eyes`)에는 묻지 않는다.
- 물을 때는 무엇이 급한지, 초기화까지 남은 시간, 리셋 없이 갈 길(예: opus high, Codex)과 그 차이를 함께 보여 준다. 몇 장 남았는지는 스크립트로 읽을 수 없으니 사용자에게 묻는다. 답은 `decisions.md`에 원문으로 적는다.
- 초기화가 가깝거나 급하지 않으면 묻지 않고 기다리거나 내려 보낸다.

## Codex 작업자

Codex 작업자도 `worker.md`와 brief를 읽고 같은 블록으로 끝낸다. 다른 점만 적는다.

- 샌드박스는 `workspace-write`다. 쓸 수 있는 곳은 띄운 폴더와 임시 폴더, 그리고 따로 연 폴더뿐이다.
- 상태 폴더에서 여는 곳은 결과 폴더 `<상태>/tasks/<id>/out` 하나다. 그 위의 brief는 쓰지 못한다. brief에는 승인 원문과 `checked`가 있어서다. 첫 줄의 결과 자리를 `<상태>/tasks/<id>/out/result.md`로 바꿔 주고, 끝나면 비서실장이 `out` 안의 `result.md`(scout는 `report.md`도)를 `<상태>/tasks/<id>/`로 옮긴다([띄우는 방법](dispatch.md#띄우는-방법)).
- **scout**는 `-C <상태>/tasks/<id>/out`으로 결과 폴더에서 띄운다. 프로젝트는 읽기만 된다. 재현하려면 써야 하는 scout는 [작업 공간](dispatch.md#작업-공간) 표의 detached worktree를 만들고, `route.py`를 `--kind run`으로 인자를 받아 그 worktree에서 띄운다. brief의 `kind`는 scout 그대로 둔다.
- **ship과 run**은 작업 공간에서 띄우고 `--add-dir <상태>/tasks/<id>/out`으로 결과 폴더의 쓰기를 연다. `route.py`에 `--workspace <작업 공간>`을 꼭 준다. 없으면 `띄워도 되나: 아니오`가 나온다.
- 상태 폴더가 임시 폴더나 그 작업 공간 안에 있으면 brief까지 쓰기 범위에 든다. 그때 `route.py`는 `띄워도 되나: 아니오`를 낸다. Claude로 보내거나 상태 폴더를 옮긴다.
- 옮기지 않은 `out/result.md`가 있으면 보고판이 `내 차례`에 올린다.
- ship은 `--approve-for-me`로 띄운다. Codex 샌드박스는 git worktree의 색인(본 저장소의 `.git` 아래)에 쓰지 못해 커밋이 막히고, 막힌 명령은 승인 요청으로 넘어간다. 이 옵션은 그 요청을 자동 검토로 보낸다. Claude 작업자의 `--permission-mode auto`와 같은 자리다. 샌드박스 밖 명령을 사람이 하나씩 확인하려면 `-a on-request`로 바꿔 띄운다. 샌드박스와 승인을 끄는 옵션은 쓰지 않는다.
- run과 scout는 `-a on-request`로 띄운다. 승인 창이 뜨면 대신 누르지 않고 사용자에게 어느 탭인지 알린다.
- push와 `gh`는 네트워크가 필요해 승인 요청으로 넘어간다. 자동 검토가 거절하면 작업자는 `needs-human`으로 끝낸다.

## 도는 작업자 옮기기

일하는 도중에는 옮기지 않는다. 다른 공급자로 가면 대화 맥락이 사라지고 디스크에 적힌 것만 남는다.

옮겨도 되는 때는 셋이 모두 맞을 때다.
- 라운드 사이다. `result.md`가 있고 화면이 쉬고 있다.
- 승인받은 행동의 `사용:`이 `실행 시작`에 멈춰 있지 않다.
- brief와 `result.md`, 작업 공간의 `git status`만으로 다음 라운드를 이어 갈 수 있다. 대화에만 있는 약속이 없다.

옮기는 것은 비서실장이 띄운 작업자뿐이다. 사용자가 직접 쓰는 세션은 건드리지 않는다.

방법:
- **같은 Claude 안에서 모델만**: 세션을 끝내고(`/exit`) 같은 pane에서 `herdr agent start <이름> --kind claude --pane <pane id> -- --resume <세션 이름이나 id> --model <별칭> --effort <effort> --permission-mode auto`. 같은 대화를 다른 모델로 다시 여는 것이라 대화가 이어지고, 같은 명령으로 되돌릴 수 있다.
- **Claude ↔ Codex**: [이어 시키기](dispatch.md#이어-시키기)대로 지난 결과에 번호를 붙이고, 같은 작업 공간에 새 작업자를 첫 줄로 띄운다. brief의 `model`과 `worker`를 고치고 `결정 기록`에 옮긴 까닭을 적는다. 옛 세션은 대화가 거기에만 남아 있으니 그대로 둔다. 옛 세션을 닫는 것은 사용자에게 묻는다.

옮길 후보를 고를 때는 일이 많이 남은 `mid`·`low` 작업부터 본다. 곧 끝나는 작업과 `high` 작업은 그대로 둔다.
