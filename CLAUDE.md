# 이 저장소에서 일할 때

- 스킬 하나 = 루트 폴더 하나(`name`과 폴더 이름이 같다). 설치한 사람의 경로가 깨지므로 폴더를 옮기거나 이름을 바꾸지 않는다.
- 새 스킬이나 지원 종료는 네 곳을 함께 고친다: `README.md`, `README.en.md`, `.claude-plugin/marketplace.json`, `skills.sh.json`. `python3 scripts/check_repo.py`가 어긋난 곳을 알려 준다.
- `SKILL.md`는 100줄 안쪽. 네 칸이 있다: 언제 쓰나(쓰지 않는 때) · 순서(단계마다 완료 기준) · 근거(무엇을 실행해 보이나) · 하지 말 것. 자세한 것은 `references/`, 계산과 검사는 `scripts/`.
- 정해진 동작은 코드로, 판단이 필요한 것만 문장으로 쓴다. 계산을 모델에게 시키지 않는다.
- 스크립트는 표준 라이브러리만. 삭제·게시·푸시·외부 전송은 기본 꺼짐이고 사용자 승인 뒤에만 한다.
- 고친 버그마다 `tests/run_tests.py`에 재현 테스트 하나.
- 모델 이름·가격·버전은 본문에 박지 않는다. 꼭 쓰면 확인한 날짜와 출처를 단다.
- 지원 종료는 폴더를 지우지 않고 안내만 남긴 `SKILL.md`(`disable-model-invocation: true`)로 바꾼다.
- 다른 사람의 스킬을 복사해 넣지 않는다. README의 "함께 쓰는 남의 스킬"에서 링크한다.
- 커밋 전에 `python3 scripts/check_repo.py --tests`.
