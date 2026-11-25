# 구조 지도 조각 (`{{MAP_SVG}}`)

템플릿의 SVG는 `viewBox="0 0 1180 640"`이다. 아래 조각을 복사해 이름·숫자만 바꾼다. 예시 이름은 지어 낸 저장소 `acme-web`이다.

## 배치

| 자리 | 좌표 |
|---|---|
| 세로 줄 3개의 왼쪽 x | 60, 450, 840 (카드 폭 280) |
| 줄 제목 | x = 200 / 590 / 980, y = 32 |
| 루트 카드 | `translate(440,60)` 300×70 |
| 카드 위쪽 y | 180(context 카드 64), 268(110), 402(130), 556(테스트 64) |

- module이 많으면 코드 파일 수(`extras.modules[].code_files`)가 큰 순서로 9개까지 그리고, 나머지는 "외 N개" 카드 하나로 묶는다.
- 카드 제목은 34자, 설명 줄은 40자까지. 넘으면 앞을 `…`로 줄인다.
- 색은 줄 수로만 정한다: 400줄 초과 `hot`, 301~400줄 `warm`, 그 밖은 `fill="var(--grid)"`. 값은 `extras.large_files`에서 가져온다.
- 선은 파일(import, 워크스페이스 설정, 문서)에서 확인한 의존성만 긋는다. 확인하지 못했으면 긋지 않는다.

## 줄 제목

```html
<text x="200" y="32" text-anchor="middle" class="node-meta" style="font-size: 11px; fill: var(--text-2); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;">apps/web</text>
```

## 루트 카드

```html
<g transform="translate(440,60)">
  <rect class="node-card accent" width="300" height="70" rx="8" />
  <circle cx="22" cy="22" r="14" class="claude-ring" />
  <circle cx="22" cy="22" r="6" class="claude-dot" />
  <text x="44" y="26" class="node-title">AGENTS.md</text>
  <text x="44" y="42" class="node-meta">프로젝트 개요 · 명령</text>
  <text x="44" y="58" class="node-meta" style="fill: var(--text-2)">60줄</text>
</g>
```

## context 카드

```html
<g transform="translate(60,180)">
  <rect class="node-card accent" width="280" height="64" rx="8" />
  <circle cx="22" cy="22" r="12" class="claude-ring" />
  <circle cx="22" cy="22" r="5" class="claude-dot" />
  <text x="42" y="26" class="node-title">apps/web/README.md</text>
  <text x="42" y="42" class="node-meta">폴더 규칙 · 실행 명령</text>
  <text x="264" y="26" text-anchor="end" class="node-kpi">48줄</text>
</g>
```

## 코드 카드 (큰 파일 줄)

```html
<g transform="translate(60,268)">
  <rect class="node-card" width="280" height="110" rx="8" />
  <text x="16" y="24" class="node-title">apps/web/src</text>
  <text x="16" y="40" class="node-meta">코드 파일 42개</text>
  <g transform="translate(16,52)">
    <rect class="hot" width="248" height="18" rx="3" />
    <text x="8" y="13" class="node-meta" style="fill: var(--red); font-weight: 600">checkout/form.tsx</text>
    <text x="240" y="13" text-anchor="end" class="node-meta" style="fill: var(--red); font-weight: 600">512</text>
  </g>
  <g transform="translate(16,74)">
    <rect class="warm" width="248" height="18" rx="3" />
    <text x="8" y="13" class="node-meta" style="fill: var(--amber); font-weight: 600">cart/list.tsx</text>
    <text x="240" y="13" text-anchor="end" class="node-meta" style="fill: var(--amber); font-weight: 600">340</text>
  </g>
</g>
```

## context가 없는 module (점선) · 없는 경로 후보 표시 (빨간 점)

```html
<g transform="translate(450,180)">
  <rect class="node-card" width="280" height="64" rx="8" stroke-dasharray="4 3" />
  <text x="16" y="26" class="node-title">scripts</text>
  <text x="16" y="42" class="node-meta">context 없음 · 코드 파일 8개</text>
  <circle cx="264" cy="20" r="5" fill="var(--red)" />
</g>
```

## 테스트 카드

```html
<g transform="translate(60,556)">
  <rect class="node-card" width="280" height="64" rx="8" />
  <circle cx="22" cy="22" r="10" fill="var(--green-soft)" />
  <circle cx="22" cy="22" r="5" class="test-dot" />
  <text x="42" y="26" class="node-title">apps/web/tests</text>
  <text x="42" y="42" class="node-meta">테스트 파일 12개</text>
</g>
```

## 선

```html
<path class="edge edge-dash" d="M500,130 C 500,160 200,160 200,180" />
<path class="edge edge-type" d="M340,300 C 400,300 400,300 450,300" />
<text x="395" y="293" text-anchor="middle" class="node-meta" style="fill: var(--accent); font-weight: 600">HTTP</text>
```

## 강점 항목 (`{{WINS_ITEMS}}`)

```html
<li>
  <div class="head"><span class="tag tag-rule">A</span>핵심 module 4개 중 4개에 context</div>
  <div class="note">루트 <code>AGENTS.md</code>에서 module README까지 두 번 만에 닿는다.</div>
</li>
```
