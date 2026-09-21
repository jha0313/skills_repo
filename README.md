# 에이전트 스킬 모음

최근 추가한 세 스킬은 한국어 사용자를 위한 지침·예시·실행 안내를 제공한다.

| 스킬 | 하는 일 |
|---|---|
| [workflow-orchestrator](workflow-orchestrator/README.md) | 조사·계획·구현·검증·리뷰를 작업자에게 맡기고 조율자는 의존성과 근거를 관리한다. |
| [eval-writer](eval-writer/README.md) | 대상 스킬 계약에서 재현 가능한 평가 사례와 루브릭을 작성·검토한다. |
| [skill-evaluator](skill-evaluator/README.md) | 격리된 실제 실행, 독립 채점, 근거 보존, 한국어 로컬 HTML/Markdown 보고서를 제공한다. |

## 설치

호스트의 스킬 설치 방식을 따른다. Claude Code에서 폴더를 직접 설치하려면 저장소 루트에서 아래처럼 실행할 수 있다. 기존 대상이 있으면 덮어쓰지 않고 건너뛴다.

```bash
mkdir -p ~/.claude/skills
for skill in workflow-orchestrator eval-writer skill-evaluator; do
  if [ -e "$HOME/.claude/skills/$skill" ] || [ -L "$HOME/.claude/skills/$skill" ]; then
    printf '기존 설치 보존: %s\n' "$skill"
  else
    cp -R "$skill" "$HOME/.claude/skills/$skill"
  fi
done
```

SKILL.md만 복사하지 말고 폴더 전체를 설치한다. Codex 등 다른 호스트는 해당 호스트의 스킬 경로를 사용한다. workflow-orchestrator에는 호스트의 subagent 기능이 필요하다. eval-writer·skill-evaluator의 실제 실행은 Python 3.11+, uv, 필요한 native eval 기능이 있는 인증된 Claude Code가 필요하다. 설치가 그 기능·권한을 대신 제공하지는 않는다.

```bash
uv run skill-evaluator/scripts/evaluate.py doctor
uv run skill-evaluator/scripts/evaluate.py --help
```

## 한국어 사용 예

```text
workflow-orchestrator로 이번 기능을 개발해보자. 중요한 결정은 나에게 물어보자.
eval-writer로 이 스킬의 평가 기준을 먼저 만들자.
skill-evaluator로 검토한 기준을 실행하고 실제 결과와 근거를 보여주자.
```

명령·flag·스키마 키·enum·스킬 이름·계약상 정확한 인용·과거 실행 근거는 원문을 유지한다. 새 안내·평가 설명·보고서 화면은 한국어이며 원시 근거를 번역해 실측 내용을 바꾸지 않는다. 기존 다른 스킬과 설명 자료는 각 폴더에 그대로 있다.
