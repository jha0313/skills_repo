# 분류 기준

어디에 있느냐보다 **다시 만들어진다는 것을 이 컴퓨터에서 확인했느냐**로 나눈다. 확인하지 못하면 ②다. 어느 칸이든 삭제는 항목별 승인 뒤에 한다.

## ① 다시 만들어지는 캐시

도구가 캐시라고 밝히고 정리·경로 명령이 있는 것만 넣는다. 명령은 2026-11-24에 로컬 도움말로 확인했다(npm 11.8, uv 0.9, pip 26.1, pnpm 11.1, Homebrew 7.0). 버전이 다르면 도움말부터 본다. 명령이 가리키는 경로가 표의 경로와 같은지도 본다.

| 흔한 경로 | 승인 전 조회(캐시를 지우지 않음) | 정리 명령(승인 뒤) | 다시 만들어지는 것 |
|---|---|---|---|
| `~/.npm/_cacache` | `npm config get cache --logs-max=1000000 --no-update-notifier` → 지울 경로는 `<출력>/_cacache` | `npm cache clean --force` | 다음 설치 때 다시 내려받음 |
| `~/.cache/uv` | `uv cache dir`, `uv cache size` | `uv cache prune`(덜 지움) / `uv cache clean` | 다시 내려받고 빌드 |
| `~/Library/Caches/pip` | `pip3 cache dir`, `pip3 cache info` | `pip3 cache purge` | 다시 내려받음 |
| pnpm store | `pnpm store path` | 안내만: `pnpm store prune` | 안 쓰는 패키지. 저장소 밖의 만료된 dlx 캐시와 전역 설치 잔여도 지운다 |
| `~/Library/Caches/Homebrew` | `brew --cache`, `brew cleanup -n --prune=all`(지울 목록만) | 안내만: `brew cleanup --prune=all` | 내려받은 것만. 캐시 밖의 옛 버전, 안 쓰는 의존 프로그램, 잠금 파일도 지운다 |

**승인 전에는 조회 칸의 명령만 친다.** 나머지 크기는 `scan.py <경로>`로 잰다. npm에는 안전한 dry-run이 없다: 11.8은 `--force`가 있으면 `--dry-run`을 줘도 캐시를 지운다(`lib/commands/cache.js`). uv·pip·pnpm의 정리 명령에도 dry-run이 없다. 다른 도구의 dry-run은 도움말과 소스로 지우지 않음을 확인하기 전에는 치지 않는다.

**안내만**인 명령은 네가 치지 않고 그 폴더도 지우지 않는다. 경로 승인보다 넓게 지우고, 미리보기에 다 나오지도 않는다(`brew cleanup -n`은 잠금 파일을 안 보여 준다). 미리보기와 함께 무엇을 더 지우는지 알리고, 사용자가 직접 치게 한다.

npm은 옵션 없이 부르면 조회만 해도 로그를 10개만 남기고 지운다. 칸의 두 옵션을 빼지 않는다(로그 하나는 새로 생긴다). `pnpm store path`는 자기 임시 파일을 만들었다 지운다.

경로 하나의 승인은 그 경로까지다. 정리 명령이 그 밖도 지우면 **안내만**으로 다룬다.

오프라인이거나 사내 저장소 접근이 끊겼으면 다시 받을 수 없다. 그때는 ②다.

## ② 검토 (사용자가 정한다)

앱 안쪽 구조에 기댄 판단은 버전이 바뀌면 틀린다. 크기·날짜와 확인 방법만 적는다.

| 종류 | 왜 검토인가 | 확인 방법 |
|---|---|---|
| `~/.cache/puppeteer`, `~/Library/Caches/ms-playwright` | 브라우저 실행 파일. 다시 받지만 돌고 있는 테스트가 깨진다 | 쓰는 프로젝트가 있는지, 브라우저 버전을 고정했는지 |
| `~/Library/Caches/<앱>` | 이름은 캐시지만 앱마다 다르다 | 앱을 끄고, 앱 설정의 "캐시 지우기"가 있으면 그것을 쓴다 |
| 자동 업데이트 폴더(`*.ShipIt` 등) | 받는 중일 수 있다 | 앱을 최신으로 올리고 끈 뒤 다시 잰다 |
| `~/Library/Application Support/<앱>` | 앱 데이터. 로컬에만 있는 것이 섞인다 | 동기화 상태, 앱의 내보내기·용량 관리 화면 |
| 앱의 가상 머신·컨테이너 이미지(`*.img`, `*.raw` 등) | 안에 작업물과 설치한 도구가 있을 수 있다. 압축본도 앱이 다시 쓸지 밖에서 알 수 없다 | 앱 안의 정리 기능이나 공식 문서. 없으면 그대로 둔다 |
| `node_modules` | 다시 설치할 수 있지만 잠금 파일이 없거나 손으로 고친 패키지는 못 되살린다 | `git status`, 잠금 파일, 마지막 커밋 날짜 |
| `~/Library/Developer/Xcode/DerivedData` | 다시 빌드한다. 오래 걸릴 수 있다 | Xcode를 끈다. 진행 중인 빌드가 없는지 |
| `~/Library/Developer/CoreSimulator/Devices` | 시뮬레이터 안의 앱 데이터가 사라진다 | `xcrun simctl list devices`로 안 쓰는 것을 고른다 |
| 세션 작업 폴더(`/private/tmp/claude-<uid>/…`) | 하나뿐인 원본이 있을 수 있다 | `session_dirs.py` 판정만. 여기서 다시 분류하지 않는다 |

`node_modules` 크기 모아 보기(프로젝트 폴더에 맞게 바꾼다):

```bash
find ~/Projects -name node_modules -type d -prune -print0 | xargs -0 du -sh | sort -rh | head -10
```

큰 파일이나 앱 이미지는 앱을 끈 뒤 `lsof <경로>`가 비었는지 본다. 비었다고 안 쓰는 것은 아니다. 열려 있으면 후보에서 뺀다.

## ③ 사용자 콘텐츠 (제안하지 않는다)

`~/Documents`, `~/Desktop`, `~/Downloads`, `~/Movies`, `~/Music`, `~/Pictures`, iCloud·클라우드 동기화 폴더, 프로젝트 소스, 휴지통. 크기만 보고하고 외장 디스크나 클라우드로 옮기는 방법을 묻는다. 동기화 폴더에서 지우면 다른 기기에서도 사라진다.
