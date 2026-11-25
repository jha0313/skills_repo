#!/usr/bin/env python3
"""token-analysis.json을 HTML 한 장으로 만든다. 외부 요청 없음, JavaScript 없음(인라인 SVG).

  python3 -I build_dashboard.py --out-dir ./token-report

결과: <out-dir>/token-report.html (권한 0600). 금액은 analyze_sessions.py가 계산한 값만 보여 준다.
"""
import argparse
import json
import os
import sys
from collections import Counter
from html import escape
from pathlib import Path

KIND_NAMES = (("cache_read", "캐시 읽기"), ("cache_write_1h", "캐시 쓰기 1시간"), ("cache_write_5m", "캐시 쓰기 5분"),
              ("output", "출력(생각 포함)"), ("input", "캐시 안 된 입력"))
GRADES = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F")
RUBRIC = (
    ("cache", "캐시 활용도", "40%", "캐시 읽기 ÷ 총 입력. 0.85 이상이면 만점."),
    ("density", "산출 밀도", "20%", "출력 ÷ 총 입력. 2% 근처가 만점."),
    ("redundancy", "파일 다시 읽기", "20%", "같은 파일을 다시 Read한 비율. 다른 구간 읽기와 수정 뒤 확인도 들어간다."),
    ("tool", "도구 사용", "20%", "출력 1,000토큰당 도구 호출 수. 2회 근처가 만점, 20회를 넘으면 크게 깎인다."),
)

CSS = """
:root{color-scheme:light;--bg:#f4f3f0;--surface:#fcfcfb;--line:#dedcd6;--ink:#0b0b0b;--ink2:#52514e;--bar:#2a78d6;--warn:#fff4d6;--warn-line:#c98500}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#111110;--surface:#1a1a19;--line:#383835;--ink:#f0efec;--ink2:#c3c2b7;--bar:#3987e5;--warn:#33290f;--warn-line:#c98500}}
*{box-sizing:border-box}
body{margin:0;padding:32px 16px 64px;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;word-break:keep-all;overflow-wrap:break-word}
main{max-width:1080px;margin:0 auto}
h1{font-size:26px;line-height:1.3;margin:0 0 4px}h2{font-size:19px;margin:40px 0 4px}h3{font-size:15px;margin:0 0 2px}
p{margin:4px 0}.sub{color:var(--ink2);font-size:14px}
.warn{background:var(--warn);border-left:4px solid var(--warn-line);padding:10px 14px;margin:12px 0;border-radius:4px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.tile,.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:16px}
.tile b{display:block;font-size:24px;line-height:1.3;font-weight:650}.tile span{color:var(--ink2);font-size:13px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:12px;margin-top:12px}
.card svg{display:block;width:100%;max-width:480px;height:auto;margin-top:12px}
svg text{fill:var(--ink2);font-size:12px;font-family:inherit}svg text.v{fill:var(--ink)}
svg .m{fill:var(--bar)}svg .m:hover{opacity:.75}svg line{stroke:var(--line)}
.scroll{overflow-x:auto;margin-top:12px;background:var(--surface);border:1px solid var(--line);border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
tr:last-child td{border-bottom:0}th{color:var(--ink2);font-weight:600;font-size:13px}td.wrap{white-space:normal;min-width:240px}
.n{text-align:right;font-variant-numeric:tabular-nums}code{font-family:ui-monospace,Menlo,monospace;font-size:.92em}
.advice{display:grid;gap:12px;margin-top:12px}.advice .card{display:grid;grid-template-columns:1fr auto;gap:0 16px;align-items:baseline}
.advice .card p{grid-column:1/-1;color:var(--ink2)}.advice b{font-variant-numeric:tabular-nums}
"""


def usd(value):
    if value is None:
        return "가격 모름"
    return f"${value:,.2f}" if value >= 0.01 or value == 0 else "$0.01 미만"


def compact(n):
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return f"{n:,}"


def session_usd(row):
    return usd(row["cost_usd"]) + ("*" if row["cost_usd"] is not None and row["unpriced_responses"] else "")


def bar(x, y, w, h, tip, horizontal):
    """끝만 둥글고 기준선 쪽은 각진 막대."""
    r = min(4, w if horizontal else h, (h if horizontal else w) / 2)
    if horizontal:
        path = f"M{x:.1f},{y:.1f}h{w - r:.1f}q{r:.1f},0 {r:.1f},{r:.1f}v{h - 2 * r:.1f}q0,{r:.1f} {-r:.1f},{r:.1f}h{r - w:.1f}z"
    else:
        path = f"M{x:.1f},{y + h:.1f}v{r - h:.1f}q0,{-r:.1f} {r:.1f},{-r:.1f}h{w - 2 * r:.1f}q{r:.1f},0 {r:.1f},{r:.1f}v{h - r:.1f}z"
    return f'<path class="m" d="{path}"><title>{escape(tip)}</title></path>'


def hbars(items, name):
    """items: (이름, 값, 표시 글자)"""
    top = max((v for _, v, _ in items), default=0) or 1
    parts = []
    for i, (label, value, text) in enumerate(items):
        y = i * 36
        width = value / top * 180
        parts.append(f'<text x="102" y="{y + 20}" text-anchor="end">{escape(label)}</text>')
        if width >= 1:
            parts.append(bar(110, y + 6, width, 20, f"{label}: {text}", True))
        parts.append(f'<text class="v" x="{117 + width:.1f}" y="{y + 20}">{escape(text)}</text>')
    return (f'<svg viewBox="0 0 360 {len(items) * 36}" role="img" aria-label="{escape(name)}">'
            f'<line x1="109.5" y1="0" x2="109.5" y2="{len(items) * 36}"/>{"".join(parts)}</svg>')


def columns(items, name, show_labels):
    """items: (이름, 값, 표시 글자). show_labels면 막대 위 값과 아래 이름을 모두 쓴다."""
    top = max((v for _, v, _ in items), default=0) or 1
    slot = 350 / max(len(items), 1)
    width = min(24, max(slot - 2, 1))
    parts = []
    for i, (label, value, text) in enumerate(items):
        x = 5 + i * slot + (slot - width) / 2
        height = value / top * 130
        if height >= 0.5:
            parts.append(bar(x, 160 - height, width, height, f"{label}: {text}", False))
        if show_labels:
            parts.append(f'<text x="{x + width / 2:.1f}" y="178" text-anchor="middle">{escape(label)}</text>')
        if value and (show_labels or i == 0):  # 값은 막대 위에(가장 큰 막대만 또는 전부)
            anchor, tx = ("middle", x + width / 2) if show_labels else ("start", x)
            parts.append(f'<text class="v" x="{tx:.1f}" y="{152 - height:.1f}" text-anchor="{anchor}">{escape(text)}</text>')
    return (f'<svg viewBox="0 0 360 186" role="img" aria-label="{escape(name)}">'
            f'<line x1="5" y1="160.5" x2="355" y2="160.5"/>{"".join(parts)}</svg>')


def pareto_caption(sessions, value):
    total = sum(value(s) for s in sessions)
    running = 0
    for i, s in enumerate(sessions, 1):
        running += value(s)
        if total and running >= total * 0.8:
            return f"위쪽 {i}개 세션이 전체의 {running / total * 100:.0f}%다(전체 {len(sessions)}개)."
    return ""


def warnings_html(data):
    t, p, n = data["totals"], data["pricing"], data["notes"]
    out = []
    if p["stale"]:
        out.append(f"가격표를 확인한 지 {p['age_days']}일 지났다. 금액이 지금 가격과 다를 수 있다.")
    if t["unpriced_responses"]:
        unknown = ", ".join(f"<code>{escape(m['model'])}</code> {m['unpriced_responses']:,}건"
                            for m in data["models"] if m["unpriced_responses"])
        out.append(f"가격을 몰라 금액에서 뺀 응답이 {t['unpriced_responses']:,}건({compact(t['unpriced_tokens'])} 토큰) 있다: {unknown}. "
                   "토큰에는 들어 있다.")
    if n["cache_write_ttl_unknown_tokens"]:
        out.append(f"캐시 쓰기 {compact(n['cache_write_ttl_unknown_tokens'])} 토큰은 5분·1시간 구분이 기록에 없어 5분 가격으로 셌다.")
    if n["broken_lines"]:
        out.append(f"읽지 못한 기록 줄이 {n['broken_lines']:,}개 있다. 실제보다 적게 세었을 수 있다.")
    for key, why in (("other_project", "기록 폴더 이름이 같은 다른 프로젝트의"), ("unclear_project", "어느 프로젝트인지 알 수 없는")):
        if n.get(f"{key}_responses"):
            out.append(f"{why} 응답 {n[f'{key}_responses']:,}건({compact(n[f'{key}_tokens'])} 토큰)은 합계에 넣지 않았다.")
    return "".join(f'<div class="warn"><b>주의</b> · {w}</div>' for w in out)


def advice_html(data):
    t = data["totals"]
    c = t["cost_by_kind"] or {}

    def stake(*kinds):
        if c:
            return usd(sum(c[k] for k in kinds))
        return compact(sum(t[k] for k in kinds)) + " 토큰"

    cards = [
        (stake("cache_read"), "긴 대화를 매번 다시 읽는 몫(캐시 읽기)",
         "관련 없는 일로 넘어갈 때는 <code>/clear</code>, 같은 일의 매듭에서는 <code>/compact</code>를 쓴다. "
         "오래 쉬어 캐시가 식은 뒤의 <code>/compact</code>는 대화 전체를 새로 읽으므로 비싸다."),
        (stake("cache_write_5m", "cache_write_1h"), "캐시를 쓰는 몫",
         "대화 중간에 모델이나 fast 모드를 바꾸면 캐시를 처음부터 다시 쓴다. 시작할 때 고르고 일이 끝날 때까지 둔다. "
         "fast 모드는 더 빠른 대신 더 비싼 요금이라 절약 수단이 아니다."),
        (stake("output"), "출력과 생각",
         "쉬운 일은 <code>/effort</code>를 낮춘다. 출력이 긴 테스트·로그는 필요한 줄만 남겨 읽힌다."),
    ]
    if t["cache_write_1h"]:
        if c:
            amount, title = usd(t["premium_1h_usd"]), "1시간 캐시에 더 낸 몫(5분 가격과의 차이)"
        else:
            amount, title = compact(t["cache_write_1h"]) + " 토큰", "1시간 캐시에 쓴 토큰(5분보다 비싸다)"
        cards.append((amount, title,
                      "5분 안에 이어지는 짧은 작업만 한다면 <code>promptCacheTtl</code> 설정이나 "
                      "<code>CLAUDE_CODE_PROMPT_CACHE_TTL=5m</code>을 시험한다. 5분 넘게 자주 쉬면 다시 쓰는 비용 때문에 손해일 수 있다."))
    cards.append((f"{len(data['models'])}개 모델", "모델 고르기",
                  "위 모델별 표에서 비싼 모델이 쉬운 일까지 맡는지 본다. 세션은 <code>/model</code>, 하위 에이전트는 설정의 모델 칸으로 바꾼다. "
                  "모델이 바뀌면 같은 일에도 토큰 수가 달라지므로 바꾼 뒤 다시 잰다."))
    if t["redundant_reads"]:
        cards.append((f"{t['redundant_reads']:,}회", "같은 파일 다시 읽기",
                      "다른 구간 읽기와 수정 뒤 확인도 들어 있다. 횟수가 많으면 검색으로 위치를 좁힌 뒤 읽게 한다."))
    return "".join(f'<div class="card"><h3>{title}</h3><b>{amount}</b><p>{body}</p></div>' for amount, title, body in cards)


def build_html(data):
    t, sessions, p = data["totals"], data["sessions"], data["pricing"]
    priced = t["cost_usd"] is not None
    value = (lambda s: s["cost_usd"] or 0) if priced else (lambda s: s["total_input"] + s["output"])
    unit = "금액" if priced else "토큰"

    if priced:
        kinds = [(name, t["cost_by_kind"][k], usd(t["cost_by_kind"][k])) for k, name in KIND_NAMES]
    else:
        kinds = [(name, t[k], compact(t[k])) for k, name in KIND_NAMES]
    top = sessions[:40]
    session_items = [(s["session_id"][:8], value(s), usd(value(s)) if priced else compact(value(s))) for s in top]
    grades = Counter(s["scores"]["grade"] for s in sessions)
    average = {k: sum(s["scores"][k] for s in sessions) / len(sessions) for k in ("cache", "density", "redundancy", "tool", "composite")}
    period = f"{data['period']['first']} ~ {data['period']['last']}" if data["period"] else "기간 모름"
    excluded = f"{t['unpriced_responses']:,}건 제외" if t["unpriced_responses"] else "모든 응답 포함"

    model_rows = "".join(
        f"<tr><td><code>{escape(m['model'])}</code></td><td class='n'>{session_usd(m)}</td><td class='n'>{m['responses']:,}</td>"
        f"<td class='n'>{compact(m['total_input'])}</td><td class='n'>{compact(m['output'])}</td><td class='n'>{m['cache_hit_ratio'] * 100:.1f}%</td></tr>"
        for m in data["models"])
    session_rows = "".join(
        f"<tr><td><code>{escape(s['session_id'][:8])}</code></td><td class='n'>{session_usd(s)}</td><td class='n'>{s['responses']:,}</td>"
        f"<td class='n'>{compact(s['total_input'])}</td><td class='n'>{compact(s['output'])}</td><td class='n'>{s['cache_hit_ratio'] * 100:.1f}%</td>"
        f"<td class='n'>{s['tool_calls']:,}</td><td class='n'>{s['redundant_reads']:,}</td>"
        f"<td class='n'>{s['scores']['composite']}</td><td>{s['scores']['grade']}</td></tr>"
        for s in sessions[:20])
    rubric_rows = "".join(
        f"<tr><td>{name}</td><td class='wrap'>{how}</td><td class='n'>{weight}</td><td class='n'>{average[key]:.1f}</td></tr>"
        for key, name, weight, how in RUBRIC)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{escape(data['label'])} 토큰 보고서</title>
<style>{CSS}</style>
</head>
<body><main>
<h1>{escape(data['label'])} 토큰 보고서</h1>
<p class="sub">{period} · 세션 {t['sessions']:,}개 · 만든 날 {escape(data['generated_on'])}</p>
<p class="sub">금액은 API 정가로 환산한 추정이다. 구독(Pro·Max 등)으로 썼다면 실제 청구액이 아니다.</p>
{warnings_html(data)}
<div class="tiles">
<div class="tile"><span>환산 금액</span><b>{usd(t['cost_usd'])}</b><span>{excluded}</span></div>
<div class="tile"><span>총 입력 토큰</span><b>{compact(t['total_input'])}</b><span>캐시 포함</span></div>
<div class="tile"><span>출력 토큰</span><b>{compact(t['output'])}</b><span>생각 포함</span></div>
<div class="tile"><span>캐시 적중률</span><b>{t['cache_hit_ratio'] * 100:.1f}%</b><span>캐시 읽기 ÷ 총 입력</span></div>
<div class="tile"><span>응답</span><b>{t['responses']:,}</b><span>도구 호출 {t['tool_calls']:,}회</span></div>
<div class="tile"><span>평균 점수</span><b>{average['composite']:.1f}</b><span>이 스킬의 어림 기준</span></div>
</div>

<h2>어디에 쓰였나</h2>
<div class="two">
<div class="card"><h3>종류별 {unit}</h3>{hbars(kinds, f'종류별 {unit}')}</div>
<div class="card"><h3>세션별 {unit}(큰 순서{', 위 40개' if len(sessions) > 40 else ''})</h3><p class="sub">{pareto_caption(sessions, value)}</p>{columns(session_items, f'세션별 {unit}', False)}</div>
</div>
<div class="scroll"><table><thead><tr><th>모델</th><th class="n">환산 금액</th><th class="n">응답</th><th class="n">총 입력</th><th class="n">출력</th><th class="n">캐시 적중</th></tr></thead><tbody>{model_rows}</tbody></table></div>

<h2>바꿔 볼 곳</h2>
<p class="sub">오른쪽 숫자는 그 항목에 걸린 크기다. 아낄 수 있는 금액이 아니다. 한 가지를 바꾸고 다시 재서 비교한다.</p>
<div class="advice">{advice_html(data)}</div>

<h2>점수</h2>
<p class="sub">네 지표를 더한 어림 점수다. 공식 기준이 아니며 일의 종류에 따라 낮아도 문제가 아닐 수 있다.</p>
<div class="two">
<div class="card"><h3>등급별 세션 수</h3>{columns([(g, grades.get(g, 0), f"{grades.get(g, 0)}개" if grades.get(g) else "0") for g in GRADES], '등급별 세션 수', True)}</div>
<div class="scroll" style="margin-top:0"><table><thead><tr><th>지표</th><th>재는 법</th><th class="n">비중</th><th class="n">평균</th></tr></thead><tbody>{rubric_rows}</tbody></table></div>
</div>

<h2>세션(큰 순서 20개)</h2>
<div class="scroll"><table><thead><tr><th>세션</th><th class="n">환산 금액</th><th class="n">응답</th><th class="n">총 입력</th><th class="n">출력</th><th class="n">캐시 적중</th><th class="n">도구</th><th class="n">다시 읽기</th><th class="n">점수</th><th>등급</th></tr></thead><tbody>{session_rows}</tbody></table></div>
<p class="sub">* 가격을 모르는 응답을 뺀 금액.</p>
<p class="sub">가격표 확인일 {escape(p['checked_on'])} · 출처 {escape(p['source_url'])}</p>
<p class="sub">겹쳐 적힌 기록 {data['notes']['duplicate_lines']:,}줄은 한 번만 셌다. 웹 검색 요금과 클라우드 사업자 가격은 들어 있지 않다.</p>
</main></body></html>
"""


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description="token-analysis.json으로 HTML 보고서를 만든다.")
    ap.add_argument("--out-dir", default="./token-report", help="analyze_sessions.py에 준 것과 같은 폴더(기본: ./token-report)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).expanduser()
    source = out_dir / "token-analysis.json"
    if not source.is_file():
        print(f"[error] {source} 이 없다. analyze_sessions.py를 먼저 실행한다.", file=sys.stderr)
        sys.exit(2)
    out = out_dir / "token-report.html"
    write_private(out, build_html(json.loads(source.read_text(encoding="utf-8"))))
    print(f"[ok] {out}")


if __name__ == "__main__":
    main()
