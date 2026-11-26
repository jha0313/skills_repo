#!/usr/bin/env python3
"""Claude·Codex 주간 사용량과 빈 메모리를 읽어 route.py가 받는 JSON으로 낸다. 표준 라이브러리만, 읽기 전용, 네트워크 없음.

  usage.py --herdr-agent <Claude 세션 이름>   # 그 세션의 화면을 herdr로 읽는다
  usage.py --claude-screen screen.txt        # 저장해 둔 화면 글(`-`는 표준 입력)

Claude: 화면 글에서 두 가지를 찾는다.
  - 상태 줄의 `| 5h -- | 7d 42% (3d5h)` 칸. 상태 줄 스크립트가 공식 `rate_limits` 값을 이 꼴로 찍을 때만 있다.
  - `/usage` 화면의 `Current week (all models)`·`Current week (Fable)` 막대. Fable 값은 여기에만 있다.
Codex: `$CODEX_HOME/sessions`(기본 ~/.codex)의 가장 새 세션 기록에 남은 주간 `rate_limits`.
못 읽은 값은 null이고 까닭은 `notes`에 정해진 낱말로 남긴다. 짐작으로 채우지 않는다.
계정 정보, 잔액, 오류 원문은 읽지도 내지도 않는다.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WEEK_H = 168
WEEK_MIN = 7 * 1440  # 이 길이의 창만 주간으로 본다
SCAN_FILES, SCAN_BYTES, CHUNK = 40, 16_000_000, 1_000_000
CLOCK_SLACK = 300  # 기록의 시각이 이만큼(초)까지 앞서는 것은 시계 차이로 본다
UTC = dt.timezone.utc
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
STATUS_7D = re.compile(r"\|[ \t]*5h[ \t]+(?:--|\d{1,3}%(?:[ \t]*\([^)\n]*\))?)[ \t]*\|[ \t]*7d[ \t]+(\d{1,3})%(?:[ \t]*\(([^)\n]*)\))?(?=[ \t]*(?:\||$)|[ \t]{2})", re.M)  # 칸의 끝까지 본다
BAR = re.compile(r"Current week \(([^)\n]+)\)\s*\n[^\n]*?(?<![\d.\-])(\d{1,3}(?:\.\d+)?)% used(?:\s*\n\s*Resets ([^\n]+))?")
RESETS = re.compile(r"(?:([A-Za-z]{3})[a-z]* (\d{1,2}) at )?(\d{1,2})(?::(\d{2}))?\s*([ap]m)(?:\s*\(([^)]+)\))?", re.I)


def span_hours(text):
    """'3d5h'·'3h20m'·'45m' → 시간."""
    parts = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?", (text or "").strip())
    if not parts or not any(parts.groups()):
        return None
    d, h, m = (int(x or 0) for x in parts.groups())
    return round(d * 24 + h + m / 60, 2)


def reset_hours(text, now):
    """'Jan 12 at 2:59am (Asia/Seoul)'·'2:59am (UTC)' → 지금부터 몇 시간. 주간 창 안의 다음 시각이 아니면 None."""
    return reset_time(text, now)[0]


def reset_time(text, now):
    """→ (시간 | None, 지난 시각인가). 지난 시각이면 그 화면은 옛 창의 것이다."""
    m = RESETS.search(text or "")
    if not m:
        return None, False
    mon, day, hour, minute, ampm, zone = m.groups()
    tz = UTC
    if zone:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(zone.strip())
        except Exception:
            return None, False
    if not 1 <= int(hour) <= 12 or (mon and mon.lower() not in MONTHS):
        return None, False
    here = now.astimezone(tz)
    clock = dict(hour=int(hour) % 12 + (12 if ampm.lower() == "pm" else 0), minute=int(minute or 0), second=0, microsecond=0)
    if mon:
        days = [(here.year + n, MONTHS[mon.lower()], int(day)) for n in (-1, 0, 1)]
    else:
        days = [(d.year, d.month, d.day) for d in (here, here + dt.timedelta(days=1))]
    hours = []
    for year, month, d in days:
        for fold in (0, 1):  # 서머타임이 끝나는 날에는 같은 시각이 두 번 온다
            try:
                when = here.replace(year=year, month=month, day=d, fold=fold, **clock)
            except ValueError:
                continue
            back = when.astimezone(UTC).astimezone(tz)
            if (back.hour, back.minute) != (when.hour, when.minute):
                continue  # 서머타임이 시작하는 날의 없는 시각
            hours.append((when.astimezone(UTC) - now.astimezone(UTC)).total_seconds() / 3600)
    if not zone:  # 시간대 이름이 없으면 시각은 짐작하지 않는다. 어느 시간대로 봐도 지난 날짜인지만 본다
        return None, bool(hours) and min(hours, key=abs) < -14
    good = [h for h in hours if 0 <= h <= WEEK_H + 1]
    if good:
        return round(min(good), 2), False
    return None, bool(hours) and min(hours, key=abs) < 0  # 가장 가까운 그 날짜가 이미 지났다


def pool(used, reset_h, source):
    used = float(used)
    return {"used": used, "reset_h": reset_h, "window_h": WEEK_H, "from": source} if 0 <= used <= 100 else None


def parse_claude(text, now):
    """화면 글 → (claude, fable). 같은 값이 여러 번 보이면 마지막(가장 아래) 것."""
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text or "")
    claude = fable = None
    for name, used, resets in BAR.findall(text):
        left, past = reset_time(resets, now)
        item = None if past else pool(used, left, "/usage 화면")  # 초기화가 지난 화면은 옛 창의 값이다
        if name.strip().lower() == "all models":
            claude = item
        elif name.strip().lower() == "fable":
            fable = item
    if claude is None:
        hits = STATUS_7D.findall(text)
        if hits:
            claude = pool(hits[-1][0], span_hours(hits[-1][1]), "상태 줄")
    return claude, fable


def weekly_in(raw, now):
    """기록 한 줄 → (본 시각, 주간 창) 또는 None. 기본 한도(`limit_id`가 없거나 codex)의 주간 창만 받는다."""
    try:
        event = json.loads(raw)
        limits = event["payload"]["rate_limits"]
        seen = dt.datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        if seen.tzinfo is None or limits.get("limit_id") not in (None, "codex"):
            return None
        if (seen - now).total_seconds() > CLOCK_SLACK:  # 시계가 틀린 기록은 지금 값이 아니다
            return None
        for window in (limits.get("primary"), limits.get("secondary")):
            if not isinstance(window, dict):
                continue
            used, minutes = window.get("used_percent"), window.get("window_minutes")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (used, minutes)):
                continue
            if 0 <= used <= 100 and minutes == WEEK_MIN:
                return seen, window
    except (ValueError, KeyError, AttributeError, TypeError):
        pass
    return None


def last_weekly(path, now):
    """기록 하나를 끝에서부터 덩어리로 읽는다. → (본 시각, 창) | None(없음) | "limit"(다 못 읽음)."""
    try:
        with open(path, "rb") as fh:
            end = size = fh.seek(0, os.SEEK_END)
            tail = b""
            while end > 0 and size - end < SCAN_BYTES:
                start = max(end - CHUNK, 0)
                fh.seek(start)
                lines = (fh.read(end - start) + tail).split(b"\n")
                tail = lines.pop(0) if start > 0 else b""  # 잘린 첫 줄은 앞 덩어리와 붙여 다시 본다
                for raw in reversed(lines):
                    if b'"rate_limits"' in raw:
                        found = weekly_in(raw, now)
                        if found:
                            return found
                end = start
            return "limit" if end > 0 else None
    except OSError:
        return "limit"  # 못 읽은 기록에 더 새 값이 있을 수 있다


def read_codex(home, now):
    """→ (값 | None, 까닭 | None). 가장 새 기록부터 본다."""
    try:
        files = sorted(((p.stat().st_mtime, p) for p in Path(home, "sessions").glob("*/*/*/rollout-*.jsonl")), reverse=True)
    except OSError:
        files = []
    if not files:
        return None, "codex-no-sessions"
    best = None
    for count, (mtime, path) in enumerate(files):
        if best is not None and mtime + CLOCK_SLACK < best[0].timestamp():
            break  # 이보다 먼저 닫힌 기록에는 더 새 값이 있을 수 없다
        if count >= SCAN_FILES:
            return None, "codex-scan-limit"
        found = last_weekly(path, now)
        if found == "limit":  # 끝까지 못 읽은 기록에 더 새 값이 있을 수 있다. 옛 값을 최신으로 내지 않는다
            return None, "codex-scan-limit"
        if found and (best is None or found[0] > best[0]):
            best = found
    if best is None:
        return None, "codex-no-weekly-limit"
    seen, window = best
    left, resets_at = None, window.get("resets_at")
    if isinstance(resets_at, (int, float)) and not isinstance(resets_at, bool):
        left = round((resets_at - now.timestamp()) / 3600, 2)
        if left <= 0:  # 마지막으로 본 뒤에 창이 새로 열렸다. 새 창의 값은 본 적이 없다
            return None, "codex-window-reset-since-last-seen"
    return {"used": float(window["used_percent"]), "reset_h": left, "window_h": round(window["window_minutes"] / 60, 2),
            "age_h": round(max((now - seen).total_seconds(), 0) / 3600, 2), "from": "Codex 세션 기록"}, None


def mem_free_pct():
    """빈 메모리 %. macOS는 memory_pressure, Linux는 /proc/meminfo."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=20).stdout
            m = re.search(r"free percentage:\s*(\d+)%", out)
            return int(m[1]) if m else None
        info = dict(re.findall(r"^(\w+):\s+(\d+)", Path("/proc/meminfo").read_text(), re.M))
        return int(info["MemAvailable"]) * 100 / int(info["MemTotal"])  # 반올림하면 문턱 바로 아래가 넘어간다
    except (OSError, KeyError, ValueError, ZeroDivisionError, subprocess.SubprocessError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Claude·Codex 주간 사용량과 빈 메모리를 JSON으로 낸다.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--herdr-agent", help="화면을 읽을 Claude 세션 이름")
    source.add_argument("--claude-screen", help="Claude 화면 글 파일(`-`는 표준 입력)")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or "~/.codex")
    parser.add_argument("--now", help="시험용 현재 시각(ISO 8601)")
    args = parser.parse_args(argv)

    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now()
    now = now.astimezone() if now.tzinfo is None else now
    screen, notes = "", []
    if args.herdr_agent:
        try:
            proc = subprocess.run(["herdr", "agent", "read", args.herdr_agent, "--source", "visible", "--lines", "200"],
                                  capture_output=True, text=True, timeout=30)
            screen = proc.stdout if proc.returncode == 0 else ""
            if proc.returncode != 0:
                notes.append(f"herdr-read-failed-exit-{proc.returncode}")
        except (OSError, subprocess.SubprocessError):
            notes.append("herdr-not-runnable")
    elif args.claude_screen:
        try:
            screen = sys.stdin.read() if args.claude_screen == "-" else Path(args.claude_screen).read_text("utf-8")
        except (OSError, ValueError):
            notes.append("screen-unreadable")
    claude, fable = parse_claude(screen, now)
    if claude is None:
        notes.append("claude-weekly-not-on-screen")
    if fable is None:
        notes.append("fable-weekly-not-on-screen")
    codex, why = read_codex(Path(args.codex_home).expanduser(), now)
    if why:
        notes.append(why)
    print(json.dumps({
        "at": now.isoformat(timespec="seconds"),
        "cli": {"claude": shutil.which("claude") is not None, "codex": shutil.which("codex") is not None},
        "claude": claude, "fable": fable, "codex": codex,
        "mem_free_pct": mem_free_pct(),
        "notes": notes,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
