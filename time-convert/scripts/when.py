#!/usr/bin/env python3
"""한 시각을 여러 시간대로 바꾸고 요일·날짜 넘어감·서머타임·남은 시간을 낸다.

  when.py "2025-11-24 14:00" --from Asia/Seoul --to 여기,Europe/London
  when.py "금 오후 1시" --from Asia/Seoul          # 오늘 이후 첫 금요일
  when.py now --to Asia/Seoul,UTC

시간대: 여기(이 컴퓨터), IANA 이름(Asia/Seoul), UTC, 또는 WHEN_PLACES에 적은 별칭.
  WHEN_PLACES="서울=Asia/Seoul,런던=Europe/London"
--to를 빼면 여기와 WHEN_PLACES의 별칭 전부를 낸다.

종료 코드: 0 정상 / 2 입력을 못 읽음 / 3 경고 있음(요일 불일치, 두 번 오는 시각, 없는 시각)
"""
import argparse
import datetime as dt
import difflib
import json
import os
import re
import sys
from zoneinfo import ZoneInfo, available_timezones

WEEK = "월화수목금토일"
EN_WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LOCAL = ("여기", "로컬", "local", "here")
NEAR = {"오늘": 0, "내일": 1, "모레": 2}
UTC = dt.timezone.utc
# 약자(EST, MST …)는 고정 시차로 계산돼 여름에 틀린다. 지역 이름과 UTC만 받는다.
NAMES = {n.lower(): n for n in available_timezones() if "/" in n or n == "UTC"}


class Bad(ValueError):
    pass


# ── 시간대 ──────────────────────────────────────────────
def canonical(name):
    if name.lower() in NAMES:
        return NAMES[name.lower()]
    city = name.lower().replace(" ", "_")
    hint = sorted(n for n in NAMES.values() if n.lower().split("/")[-1] == city)
    hint = hint or difflib.get_close_matches(name, list(NAMES.values()), 3)
    raise Bad(f"모르는 시간대: {name!r}. IANA 이름(예: Asia/Seoul)을 쓰거나 WHEN_PLACES에 별칭을 적는다. 약자는 받지 않는다."
              + (f" 혹시: {', '.join(hint[:3])}" if hint else ""))


def local_zone():
    name = os.environ.get("TZ", "").lstrip(":")
    if not name:
        m = re.search(r"zoneinfo[^/]*/(.+)$", os.path.realpath("/etc/localtime"))
        name = m.group(1) if m else ""
    if name.lower() not in NAMES:
        raise Bad("이 컴퓨터의 시간대를 알 수 없다. TZ에 IANA 이름을 넣거나 --from·--to에 직접 적는다.")
    return NAMES[name.lower()]


def load_places(text):
    places = {}
    for item in (x.strip() for x in text.split(",")):
        name, eq, zone = (x.strip() for x in item.partition("="))
        if item and (not eq or not name or name.lower() in LOCAL):
            raise Bad(f"WHEN_PLACES의 {item!r}를 못 읽었다. 형식: 이름=IANA이름,이름=IANA이름")
        if item:
            places[name] = canonical(zone)
    return places


def resolve(name, places):
    """(IANA 이름, 화면에 쓸 이름)"""
    key = name.strip().lower()
    if key in LOCAL:
        return local_zone(), "여기(이 컴퓨터)"
    for alias, zone in places.items():
        if alias.lower() == key:
            return zone, alias
    zone = canonical(name.strip())
    return zone, next((a for a, z in places.items() if z == zone), zone)


# ── 입력 읽기 ───────────────────────────────────────────
def parse(text, now):
    """(시간대 없는 시각, 적힌 요일 또는 None, 가정 목록). 남는 글자가 있으면 오류."""
    rest = re.sub(r"(?<=\d)[Tt](?=\d)", " ", text.strip())

    def take(pattern):
        nonlocal rest
        m = re.search(pattern, rest, re.I)
        if m:
            rest = rest[:m.start()] + " " + rest[m.end():]
        return m

    today, notes, day = now.date(), [], None
    m = (take(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
         or take(r"(?:(\d{4})년\s*)?(?<!\d)(\d{1,2})월\s*(\d{1,2})일")
         or take(r"(?<![\d/])()(\d{1,2})/(\d{1,2})(?![\d/])"))
    if m:
        year = int(m.group(1) or today.year)
        try:
            day = dt.date(year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            raise Bad(f"없는 날짜: {m.group(0).strip()!r}") from None
        if not m.group(1):
            notes.append(f"연도가 없어 {year}년으로 봤다")
    near = take(r"내일\s*모레|오늘|내일|모레")
    if near:
        if day:
            raise Bad(f"날짜가 두 개다: {text!r}")
        day = today + dt.timedelta(days=NEAR["모레" if "모레" in near.group(0) else near.group(0)])
        notes.append(f"'{near.group(0)}'를 {day}({WEEK[day.weekday()]})로 봤다")
    said = None
    m = take(r"\(\s*([월화수목금토일])(?:요일)?\s*\)|(?<!\w)([월화수목금토일])(?:요일)?(?=에?(?:\s|$|\d))")
    if m:
        said = WEEK.index(m.group(1) or m.group(2))
    m = take(r"(?<!\w)\(?(mon|tue|wed|thu|fri|sat|sun)(?:day|sday|nesday|rsday|urday|s|rs|r)?\)?(?!\w)")
    if m:
        said = EN_WEEK.index(m.group(1).lower())
    half = take(r"오전|오후|(?<![a-z])[ap]m(?![a-z])")
    m = take(r"(?<!\d)(\d{1,2})\s*(?::\s*(\d{2})|시\s*(?:(\d{1,2})\s*분|(반))?)(?![\d:])")
    if not m:
        raise Bad(f"시각을 못 읽었다: {text!r}. 예: 2025-11-24 14:00")
    if rest.strip(" ,·에\t"):
        raise Bad(f"읽지 못한 부분이 있다: {rest.strip()!r}. 날짜와 시각만 적고 시간대는 --from으로 준다.")
    hour, minute = int(m.group(1)), int(m.group(2) or m.group(3) or (30 if m.group(4) else 0))
    if half:
        pm = half.group(0).lower() in ("오후", "pm")
        if not pm and hour > 12:
            raise Bad(f"오전과 {hour}시가 맞지 않는다")
        hour = hour % 12 + 12 if pm and hour <= 12 else hour % 12 if not pm else hour
    if hour > 23 or minute > 59:
        raise Bad(f"없는 시각: {hour}:{minute:02d} (자정은 다음 날 00:00으로 적는다)")
    if day is None:
        day = today + dt.timedelta(days=0 if said is None else (said - today.weekday()) % 7)
        why = "날짜가 없어 오늘" if said is None else "요일만 있어"
        notes.append(f"{why} {day}({WEEK[day.weekday()]})로 봤다")
    return dt.datetime(day.year, day.month, day.day, hour, minute), said, notes


# ── 계산 ────────────────────────────────────────────────
def instants(naive, tz):
    """그 벽시계 시각이 가리키는 순간들. 보통 1개, 두 번 오면 2개, 없는 시각이면 0개."""
    found = []
    for fold in (0, 1):
        u = naive.replace(tzinfo=tz, fold=fold).astimezone(UTC)
        if u not in found and u.astimezone(tz).replace(tzinfo=None) == naive:
            found.append(u)
    return sorted(found)


def offset(delta):
    minutes = int(delta.total_seconds() // 60)
    h, m = divmod(abs(minutes), 60)
    return f"UTC{'-' if minutes < 0 else '+'}{h}" + (f":{m:02d}" if m else "")


def span(seconds):
    minutes = int(abs(seconds) // 60)
    if not minutes:
        return "지금"
    d, rest = divmod(minutes, 1440)
    h, m = divmod(rest, 60)
    return (f"{d}일 " if d else "") + f"{h}시간 {m}분 " + ("뒤" if seconds > 0 else "전")


def row(u, zone, label, src_day):
    tz = ZoneInfo(zone)
    d = u.astimezone(tz)
    start = dt.datetime(d.year, d.month, d.day, tzinfo=tz)
    before, after = start.utcoffset(), (start + dt.timedelta(days=1)).utcoffset()
    twice = len(instants(d.replace(tzinfo=None), tz)) == 2
    return dict(place=label, zone=zone, local=d.isoformat(timespec="minutes"), weekday=WEEK[d.weekday()],
                utc_offset=offset(d.utcoffset()), day_diff=(d.date() - src_day).days,
                offset_change=f"{offset(before)} → {offset(after)}" if before != after else None,
                repeated=("두 번째" if d.fold else "첫 번째") if twice else None)


def line(r):
    tail = [r["utc_offset"]]
    if r["day_diff"]:
        tail.append({1: "다음 날", -1: "전날"}.get(r["day_diff"], f"{r['day_diff']:+d}일"))
    if r["offset_change"]:
        tail.append(f"이날 시차가 바뀜: {r['offset_change']}")
    if r["repeated"]:
        tail.append(f"두 번 오는 시각 중 {r['repeated']}")
    return f"  {r['place']}: {r['local'][:10]}({r['weekday']}) {r['local'][11:16]} ({', '.join(tail)})"


def convert(a):
    places = load_places(os.environ.get("WHEN_PLACES", ""))
    src, src_label = resolve(a.src, places)
    tz = ZoneInfo(src)
    now = dt.datetime.now(UTC)
    if a.now:
        base = instants(parse(a.now, now.astimezone(tz))[0], tz)
        if not base:
            raise Bad(f"--now가 {src}에 없는 시각이다")
        now = base[0]
    targets, seen = [], set()
    names = a.to.split(",") if a.to else ["여기", *places]
    for name in [a.src, *names]:
        zone, label = resolve(name, places)
        if zone not in seen:
            seen.add(zone)
            targets.append((zone, label))
    notes, warnings = [], []
    if a.when.strip().lower() == "now":
        moments, naive = [now], now.astimezone(tz).replace(tzinfo=None)
    else:
        naive, said, notes = parse(a.when, now.astimezone(tz))
        moments = instants(naive, tz)
        if said is not None and said != naive.weekday():
            warnings.append(f"{naive:%Y-%m-%d}는 {WEEK[said]}요일이 아니라 {WEEK[naive.weekday()]}요일이다({src_label} 기준)")
        if len(moments) == 2:
            warnings.append(f"{naive:%Y-%m-%d %H:%M}은 {src_label}에서 두 번 온다(시계가 뒤로 감). 어느 쪽인지 정해야 한다")
        if not moments:
            gap = abs(naive.replace(tzinfo=tz, fold=1).utcoffset() - naive.replace(tzinfo=tz).utcoffset())
            warnings.append(f"{naive:%Y-%m-%d %H:%M}은 {src_label}에 없는 시각이다(시계가 {int(gap.total_seconds() // 60)}분 앞으로 감). "
                            f"변환하지 않았다. 다시 정한다: {naive - gap:%H:%M} 또는 {naive + gap:%H:%M}")
    results = [dict(utc=u.strftime("%Y-%m-%dT%H:%MZ"),
                    rows=[row(u, z, label, naive.date()) for z, label in targets],
                    from_now=span((u - now).total_seconds()),
                    from_now_minutes=int((u - now).total_seconds() / 60)) for u in moments]
    return dict(input=a.when, source=src, source_label=src_label, now=now.astimezone(tz).isoformat(timespec="minutes"),
                results=results, notes=notes, warnings=warnings)


def main(argv):
    ap = argparse.ArgumentParser(description="한 시각을 여러 시간대로 바꾼다.")
    ap.add_argument("when", help='"2025-11-24 14:00", "11/24(월) 오후 2시", "금 13:00", "내일 9시 30분", now')
    ap.add_argument("--from", dest="src", default="여기", help="입력 시각의 시간대 (기본 여기)")
    ap.add_argument("--to", help="쉼표로 나눈 시간대 (기본 여기 + WHEN_PLACES)")
    ap.add_argument("--now", help="기준 시각 (--from 시간대, 기본 지금)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        out = convert(a)
    except Bad as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    except OverflowError:
        print("오류: 계산할 수 없는 날짜다", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"입력: {out['input']} ({out['source_label']} 기준)")
        for i, res in enumerate(out["results"], 1):
            if len(out["results"]) > 1:
                print(f"[{i}번째로 오는 경우]")
            print("\n".join(line(r) for r in res["rows"]))
            print(f"  지금부터 {res['from_now']}" if res["from_now"] != "지금" else "  지금")
        for text in out["notes"]:
            print(f"가정: {text}")
        for text in out["warnings"]:
            print(f"경고: {text}")
    return 3 if out["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
