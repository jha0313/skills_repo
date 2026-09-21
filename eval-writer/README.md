# eval-writer

스킬 평가 기준 작성을 돕는 얇은 스킬이다. 대상 계약을 읽고 기존 **skill-evaluator**로 서로 다른 사례, 관찰 가능한 수준별 루브릭, 도구 mock, 백업, 검토 가능한 인계를 만든다.

전체 eval-writer 폴더를 skill-evaluator 옆에 설치하거나 두 스킬을 일반 스킬 묶음으로 사용할 수 있게 한다. 두 번째 runner·judge 프레임워크는 포함하지 않는다.

요청 예시:

```text
내 release-checklist 스킬의 eval 기준을 기본 10개 사례로 작성해보자.
/path/to/my-skill에 설치된 스킬의 BASIC binary 평가 기준을 만들자.
oncall 스킬의 라우팅과 실패 처리를 deep 모음으로 점검할 기준을 만들자.
검토한 사례를 정식 YAML과 함께 JSONL로도 내보내자.
```

저장소 루트에서 직접 CLI를 쓴다면:

```bash
uv run skill-evaluator/scripts/evaluate.py prepare /path/to/my-skill --local
uv run skill-evaluator/scripts/evaluate.py validate /path/to/my-skill/evals/eval_criteria.yaml
```

BASIC은 두 명령 모두 --basic, Binary는 --binary, deep은 --deep을 추가한다. 설치 캐시 사본을 대상으로 하면 준비 때 --source /path/to/writable/skill을 준다. 스킬은 현재 evaluator help로 정확한 인자를 확인한다.

준비 단계는 실제 모델을 사용해 분석·기준을 생성할 수 있다. 대상 옆에 기준을 쓰고 타임스탬프 백업을 보존한다. 대상을 실행하거나 채점하지는 **않는다**. 최종 작성 보고는 기준·manifest·분석·검토 표에 연결하고 검증·남은 빈틈·다음 실행 명령을 제시한다.

정식 실행 형식은 evaluator YAML이며 JSON으로 직렬화할 수 있다. JSONL은 선택적 교환 형식이다. 줄마다 완전한 사례 하나와 기본값·모드·출처를 보존한 sidecar를 만든다. YAML 전용 검증기에 원시 JSONL을 전달하지 않는다.

[SKILL.md](SKILL.md)와 [작성 가이드](references/authoring-guide.md)를 읽는다. 정식 스키마·척도는 [skill-evaluator](../skill-evaluator/README.md)에 있다. 스키마 유효성은 스킬의 동작을 입증하지 않는다. 실제 red/green 실행과 스킬 사용 유무 비교는 서로 다른 근거다.

## 개발 당시 작성 smoke 근거

다음은 **한국어 현지화 이전**인 2026-09-19의 기록이다. 실제 Claude Code 세션이 자연어 기준 작성 요청에서 eval-writer를 선택하고 임시 Harbor release-brief 스킬에 기존 evaluator 작성자를 호출했다. 대상별 10개 사례(2/1/2/2/3, 서로 다른 의미 질문25개)를 만들었다. 자연·부정 라우팅, 소스 ID, 미확인 kind, 호환성을 깨는 migration, 인증 리뷰, 입력에 주입된 지시, 버전·파일 누락을 포함했다.

첫 Likert 초안은 critical 검사11개에 Binary 수준을 잘못 사용했다. 잘못된 초안을 보존하고 evaluator 도우미로 정확한 바이트를 백업한 뒤 소스 규칙·사례 prompt를 바꾸지 않고 수준만 교정했다. 당시 CLI는 `Criteria valid`라고 보고했다. **한 번에 자동 성공한 것은 아니다.** 대상 실행·채점은 하지 않았으며 확인한 범위는 라우팅, 기준 생성, 교정·백업, 스키마 검증이다. 이 과거 기록을 한국어판의 추가 실제 실행 검증으로 제시하지 않는다.
