# workflow-orchestrator

**조율만 하는 orchestrator**를 위한 작고 독립적인 스킬이다. 조율자 한 명이 사용자와 대화하고 작업자들이 조사·계획·구현·검증·리뷰·승인된 전달을 수행한다. 조율자는 구현을 대신하지 않고 의존성과 근거를 관리한다.

세미나의 흐름을 따른다.

```text
Intake → Context → Plan → Implement → Verify → Review & Land
             ↑                              ↓
             └──── Monitor → lint / rule / eval 피드백
```

스크립트, hook, daemon, background supervisor, 별도 상태 프레임워크, 터미널 backend, 필수 모델은 포함하지 않는다. 호스트의 subagent와 기존 저장소 도구를 쓴다. 호스트의 위임 기능이 필요하며 Git 병렬 변경에는 적절한 worktree를 사용한다. 지침을 설치하는 것만으로 이런 기능이나 OS sandbox가 생기지 않는다.

## 사용하기

호스트의 일반 스킬 설치 방식으로 폴더 전체를 설치한다. Claude Code는 보통 `.claude/skills/` 아래 SKILL.md가 있는 폴더를 발견하고 다른 호스트는 설정된 스킬 디렉터리를 사용한다. 프로젝트 지식은 특정 에이전트에 종속되지 않으며 `CLAUDE.md`만 의존하지 않고 해당 저장소 지침을 따른다.

요청 예시:

```text
workflow-orchestrator로 이 기능 개발을 조율해보자. 프로젝트 작업은 모두 위임하자.
저장소를 파악하고 계획을 검토한 뒤 격리된 작업자로 구현하자.
GATE와 VERIFY 근거는 구분해서 보여주고 지금은 로컬 변경까지만 하자.
```

```text
workflow-orchestrator로 이 사이트의 페이지별 Lighthouse 기준값을 읽기 전용으로 조사하자.
작업자가 경로와 접근 제약을 조사하고, 측정 담당자가 반복 가능한 결과를 수집하고,
리뷰어가 근거를 확인하게 하자. 코드는 바꾸지 말고 구현 제안 전에 실제 측정 결과를 보고하자.
```

Lighthouse 예시는 페이지·기기·인증 상태, 브라우저·Lighthouse 버전, throttling/cache 정책, 반복 횟수, 집계 방식, 기능 제약을 성공 검사에 명시해야 한다. Lab 점수가 높아졌다는 사실만으로 실제 사용자 경험 개선을 입증하지 못한다. 이는 과제별 브리프 선택이며 스킬이 Lighthouse runner를 설치하거나 있다고 가정하는 것은 아니다.

목표가 명확하면 바로 시작한다. 중요한 결정이 빠졌으면 짧게 인터뷰한다. 기존 승인은 유지되며 commit/push/merge/배포는 사용자·호스트가 이미 승인한 정확한 범위를 따른다. 읽기 전용 측정은 최적화 변경까지 승인하지 않는다.

전체 흐름과 짧은 브리프는 [SKILL.md](SKILL.md), 재사용할 위임·검토 프롬프트는 [orchestration-prompts.md](references/orchestration-prompts.md)에 있다. 이 패키지는 작게 유지하며 원본 Firstmate 배포판의 감독·복구·backend 보장을 주장하지 않는다.

## 실제 확인한 smoke 범위

아래는 버전 1.2.0의 프롬프트 보강과 한국어 현지화 **이전** 기록이다. 보강·번역된 지침에 대한 추가 실제 실행 검증으로 해석하지 않는다.

2026-09-19 원래 probe는 이전 이름 `firstmate-lite`로 실행했다. 보존된 실행 원문은 바꾸지 않았다.

실제 Claude Code 세션이 스킬을 로드하고 4줄 읽기 전용 fixture 조사를 native Explore 작업자 한 명에게 위임했다. 부모는 Skill·Agent만 호출하고 작업자만 프로젝트 파일을 읽었다. 최종 답변은 정확한 줄 수·라벨·원문 인용을 제시했고 fixture는 그대로였다. Frontmatter 검증도 통과했다.

두 번째 실제 세션은 구현 작업자 한 명이 3줄 Python 공백 정규화 함수를 수정하고 별도 리뷰·검증 작업자가 확인했다. 부모는 다시 Skill·Agent만 호출했다. 제공한 테스트 2개는 변경 전 실패, 변경 후 통과, 독립 재실행도 통과했다(**GATE**). 독립 리뷰어는 탭·개행·빈 입력·대소문자 등 직접 경계 사례 8개를 별도로 확인했다(**VERIFY**). 작업자만 소스 한 줄을 바꿨고 테스트 파일은 원래 해시를 유지했다. Fixture에서 commit/merge/배포/외부 발행은 하지 않았다.

이 작은 probe는 자연 로드, 위임, 부모 편집 금지, 작은 로컬 변경, 독립 리뷰, GATE/VERIFY 분리 보고를 확인한다. 전체 운영 연동, 브라우저 검증, 병렬 worktree 통합, 배포, 중단 복구를 보장하지 않는다.

`workflow-orchestrator`로 이름을 바꾼 뒤 실제 Skill 도구를 통해 두 probe를 다시 실행했다. 조율자는 Skill·Agent만 사용했다. 읽기 전용 fixture는 그대로였고 변경 fixture는 원래 해시의 테스트 2개를 통과했으며 별도 작업자가 직접 공백 경계 사례 7개를 확인했다. 로드·위임 동작의 회귀 확인이지 운영 기능 검증이 아니다.

[kunchenguid/firstmate](https://github.com/kunchenguid/firstmate)에서 영감을 받았다. [참고 revision과 MIT 고지](THIRD_PARTY_NOTICES.md)를 확인할 수 있다.
