#!/usr/bin/env python3
"""작업 하나를 어느 공급자·모델·effort로 보낼지 정한다. 표준 라이브러리만, 읽기 전용, 네트워크 없음.

  usage.py --herdr-agent <Claude 세션> | route.py --kind ship --level mid --task <id> --workspace <작업 공간> --usage -
  route.py --kind scout --level high --other-eyes --usage usage.json --json

--kind   ship | run | scout
--level  high(머지·보안·돈·설계·검증처럼 틀리면 비싼 일) | mid(보통 구현) | low(조사·대조·기계적 수정·반복)
--other-eyes  Claude가 만든 것을 다른 공급자가 독립으로 봐야 할 때
--urgent      오늘 안에 끝나야 할 때. 리셋권을 물을지 판단할 때만 쓴다
--usage  usage.py가 낸 JSON 파일(`-`는 표준 입력). 없으면 사용량을 모르는 것으로 본다
--without claude|codex  그 공급자를 쓰지 않는다(여러 번 가능)
--task   작업 id. 주면 Codex 인자에 그 작업의 결과 폴더(tasks/<id>/out) 실제 경로를 넣는다
--workspace  작업자를 띄울 작업 공간. 상태 폴더가 그 안에 있으면 Codex로 띄우지 않는다. ship·run을 Codex로 띄우려면 꼭 준다
--not-model  이 별칭의 Claude 모델은 고르지 않는다. 만든 모델과 다른 Claude 모델이 봐야 할 때

모델 이름은 여기 박지 않는다. Claude는 별칭(fable·opus·sonnet), Codex는 설정 파일의 기본 모델을 쓴다.
Codex 모델을 정하려면 상태 폴더의 routing.json에 {"codex_model": "…", "codex_review_model": "…"}을 둔다.
리셋권은 쓰지 않는다. 물을 때인지만 알려 준다.
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import shlex
import sys
from pathlib import Path

OUT = 97          # 이만큼 썼으면 닿은 것으로 본다(%)
TIGHT_USED = 85   # 속도와 상관없이 아낀다(%)
SPARE_AT_RESET = 70  # 지금 속도로 초기화 때 이만큼도 못 쓰면 남는다(%)
NEAR_RESET_H = 6  # 초기화가 이 안이면 남은 것은 곧 사라진다
LONG_RESET_H = 24  # 초기화가 이보다 멀어야 리셋권을 물을 만하다
MIN_ELAPSED_H = 12  # 창이 막 열렸을 때 속도를 부풀리지 않으려는 최소 경과 시간
STALE_H = 24      # 이보다 오래된 값은 믿지 않는다(닿은 값은 예외: 창 안에서 사용량은 줄지 않는다)
WEEK_H = 168
MAX_WINDOW_H = 192  # 주간 창이라 할 수 있는 가장 긴 길이
SNAPSHOT_MAX_MIN = 60  # usage.py를 돌린 지 이보다 오래됐으면 다시 읽게 한다
MEM_MIN_FREE = 30  # 빈 메모리가 이보다 낮으면 새 작업자를 띄우지 않는다(%)

KINDS, LEVELS = ("ship", "run", "scout"), ("high", "mid", "low")
BASE = {  # level → kind → (Claude 별칭, effort)
    "high": {k: ("fable", "high") for k in KINDS},
    "mid": {"ship": ("opus", "high"), "run": ("opus", "medium"), "scout": ("opus", "medium")},
    "low": {k: ("sonnet", "medium") for k in KINDS},
}
WORD = {"out": "닿음", "tight": "빠듯", "ok": "보통", "spare": "남음", "unknown": "모름"}
NAME = {"claude": "Claude 주간", "fable": "Fable 주간", "codex": "Codex 주간"}


class BadUsage(ValueError):
    pass


def number(value, where, low=None, high=None, optional=True):
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise BadUsage(f"{where}이(가) 숫자가 아님")
    if (low is not None and value < low) or (high is not None and value > high) or abs(value) > 1e9:
        raise BadUsage(f"{where}이(가) 범위 밖")
    return float(value)


def clean(pool, key, elapsed=0.0):
    """입력 경계에서 한 번 검사한다. → {"used", "left", "window", "age"} 또는 None(값 없음).
    elapsed는 사용량을 읽은 뒤 지난 시간이다. 남은 시간에서 빼고 나이에 더한다."""
    if pool is None:
        return None
    if not isinstance(pool, dict):
        raise BadUsage(f"{key}이(가) 객체가 아님")
    used = number(pool.get("used"), f"{key}.used", 0, 100)
    if used is None:
        return None
    window = number(pool.get("window_h"), f"{key}.window_h", 1, MAX_WINDOW_H) or WEEK_H
    left = number(pool.get("reset_h"), f"{key}.reset_h")
    if left is not None and left > window:
        left = None  # 창보다 긴 남은 시간은 있을 수 없다. 시각을 모르는 것으로 본다
    age = number(pool.get("age_h"), f"{key}.age_h", 0)
    if elapsed:
        left, age = (None if left is None else left - elapsed), (age or 0.0) + elapsed
    return {"used": used, "left": left, "window": window, "age": age}


def pace(pool):
    """clean()을 거친 한도 하나 → (상태, 설명). 위에서부터 처음 맞는 줄."""
    if pool is None:
        return "unknown", "사용량을 읽지 못함"
    used, left = pool["used"], pool["left"]
    if left is not None and left <= 0:
        return "unknown", "초기화 시각이 지난 값이라 다시 읽어야 한다"
    age = pool["age"] or 0.0
    if left is not None and age + left > pool["window"]:
        return "unknown", "값을 본 뒤에 창이 바뀌어 다시 읽어야 한다"
    if age > STALE_H and (used < OUT or left is None):  # 닿은 값은 같은 창인 것이 확인될 때만 묵혀 쓴다
        return "unknown", f"{age:.0f}시간 전 값이라 다시 읽어야 한다"
    if used >= OUT:
        return "out", f"{used:.0f}% 사용" + (f", 초기화까지 {left:.0f}시간" if left is not None else "")
    if left is None:
        return ("tight" if used >= TIGHT_USED else "ok"), f"{used:.0f}% 사용, 초기화 시각 모름"
    if left <= NEAR_RESET_H:
        return "spare", f"{used:.0f}% 사용, {left:.0f}시간 뒤 초기화라 남은 것은 사라진다"
    seen_left = left + age  # 값을 본 때 기준으로 속도를 잰다
    rate = used / max(pool["window"] - seen_left, MIN_ELAPSED_H)  # 시간당 %
    at_reset = used + rate * seen_left
    if at_reset >= 100:
        return "tight", f"{used:.0f}% 사용, 이 속도면 {max((100 - used) / rate - age, 0):.0f}시간 뒤 닿는다(초기화까지 {left:.0f}시간)"
    if used >= TIGHT_USED:
        return "tight", f"{used:.0f}% 사용(초기화까지 {left:.0f}시간)"
    if at_reset < SPARE_AT_RESET:
        return "spare", f"{used:.0f}% 사용, 이 속도면 초기화 때 {at_reset:.0f}%뿐(초기화까지 {left:.0f}시간)"
    return "ok", f"{used:.0f}% 사용, 이 속도면 초기화 때 {at_reset:.0f}%"


def decide(kind, level, usage, other_eyes=False, urgent=False, without=(), elapsed_h=0.0, not_model=None):
    """→ {"provider", "model", "effort", "role", "why", "state", "detail", "reset", "spawn", "spawn_why", "how"}."""
    if not isinstance(usage, dict):
        raise BadUsage("사용량이 JSON 객체가 아님")
    pools = {k: clean(usage.get(k), k, elapsed_h) for k in NAME}
    mem = number(usage.get("mem_free_pct"), "mem_free_pct", 0, 100)
    cli = usage.get("cli", {})  # 없는 것과 null은 다르다. 적었으면 형이 맞아야 한다
    if not isinstance(cli, dict):
        raise BadUsage("cli가 객체가 아님")
    for k in ("claude", "codex"):
        if k in cli and not isinstance(cli[k], bool):
            raise BadUsage(f"cli.{k}가 true·false가 아님")
    claude_cli, codex_cli = cli.get("claude"), cli.get("codex")
    state, detail = {}, {}
    for k in NAME:
        state[k], detail[k] = pace(pools[k])
    # Claude는 CLI가 없어도 호스트의 subagent로 띄울 수 있다. Codex는 CLI가 없으면 못 띄운다.
    have = {"claude": "claude" not in without, "codex": "codex" not in without and codex_cli is not False}
    claude_ok = have["claude"] and state["claude"] != "out"
    codex_ok = have["codex"] and state["codex"] != "out"
    why = []

    def no(p):
        return f"{p.capitalize()}를 쓸 수 없다" if not have[p] else f"{NAME[p]} 한도에 닿았다({detail[p]})"

    def out(provider, model=None, effort=None, role=None, ask_reset=True):
        if provider is None:
            spawn, spawn_why = False, "보낼 곳이 없다"
        elif mem is None:
            spawn, spawn_why = None, "빈 메모리를 읽지 못함. 직접 보고 정한다"
        elif mem < MEM_MIN_FREE:  # 표시는 내림한다. 올림하면 문턱과 같아 보인다
            spawn, spawn_why = False, f"빈 메모리 {math.floor(mem * 10) / 10:g}% < {MEM_MIN_FREE}%. 끝난 세션을 닫을지 묻거나 기다린다"
        else:
            spawn, spawn_why = True, f"빈 메모리 {math.floor(mem * 10) / 10:g}%"
        reset = reset_advice(level, urgent, state, pools, provider, role, have)
        if reset == "fable" and not_model == "fable":  # 쓰지 않을 모델의 한도를 채울 까닭이 없다
            reset = None
        return {"provider": provider, "model": model, "effort": effort, "role": role, "why": why,
                "state": state, "detail": detail, "spawn": spawn, "spawn_why": spawn_why,
                "how": "subagent" if provider == "claude" and claude_cli is False else None,
                # 메모리 때문에 못 띄울 때는 리셋해도 소용없다. 다시 잰 뒤에 판단한다
                "reset": reset if ask_reset and not (mem is not None and mem < MEM_MIN_FREE) else None}

    if other_eyes:
        if codex_ok:
            why.append("다른 눈이 필요한 일이라 Codex로 보낸다")
            return out("codex", effort="high", role="review")
        why.append(f"다른 눈이 필요하지만 {no('codex')}. Claude로 보내면 독립 리뷰가 아니다. "
                   "Claude의 다른 모델로 볼지 사용자에게 묻고, 그러기로 하면 --other-eyes 대신 --not-model <만든 모델>로 다시 돌린다")
        return out(None, ask_reset=False)
    if not claude_ok:
        why.append(no("claude"))
        if codex_ok:
            why.append("Codex로 보낸다")
            return out("codex", effort="high", role="build")
        why.append(no("codex") + ". 초기화를 기다리거나 사용자에게 묻는다")
        return out(None)
    if level != "high" and codex_ok and state["codex"] != "tight":
        if state["claude"] == "tight":
            why.append(f"Claude가 빠듯하다({detail['claude']}). 어려운 일만 Claude에 남기고 이 일은 Codex로 보낸다")
            return out("codex", effort="high", role="build")
        if state["codex"] == "spare" and state["claude"] != "spare":
            why.append(f"Codex가 남는다({detail['codex']}). 구독을 다 쓰도록 이 일은 Codex로 보낸다")
            return out("codex", effort="high", role="build")

    model, effort = BASE[level][kind]
    why.append(f"{kind}·{level}의 기본은 {model} {effort}")
    if model == "fable" and state["fable"] in ("out", "tight"):
        model = "opus"
        why.append(f"Fable이 {WORD[state['fable']]}({detail['fable']})이라 opus로 내린다")
    if state["claude"] == "tight":
        if level == "mid":
            model, effort = "sonnet", "high"
            why.append(f"Claude가 빠듯하고({detail['claude']}) Codex로 보낼 수 없어 sonnet으로 내린다")
        elif level == "high":
            why.append(f"Claude가 빠듯하지만({detail['claude']}) 어려운 일이라 Claude에 남긴다")
    elif state["claude"] == "spare" and level != "high":
        if level == "mid" and kind == "ship" and state["fable"] == "spare":
            model, effort = "fable", "medium"
            why.append(f"Claude와 Fable이 남는다({detail['fable']}). fable medium으로 올린다")
        elif effort == "medium":
            effort = "high"
            why.append(f"Claude가 남는다({detail['claude']}). effort를 high로 올린다")
    if model == not_model:
        model = "opus" if model != "opus" else ("fable" if state["fable"] not in ("out", "tight") else "sonnet")
        effort = "high"
        why.append(f"{not_model}이 만든 것을 보는 일이라 {model} high로 바꾼다")
    return out("claude", model, effort)


def reset_advice(level, urgent, state, pools, provider, role, have):
    """리셋권을 물을 때인가. 급하고, 한도에 닿았고, 초기화가 멀고, 다른 길이 모자랄 때만."""
    def far(key):
        return pools[key] is not None and pools[key]["left"] is not None and pools[key]["left"] > LONG_RESET_H

    if not urgent or not have["claude"] or role == "review":  # 독립 리뷰는 Claude 한도와 상관없다
        return None
    if state["claude"] == "out" and far("claude") and (provider is None or level == "high"):
        return "weekly"
    if level == "high" and state["claude"] != "out" and state["fable"] == "out" and far("fable"):
        return "fable"
    return None


def launch(result, kind, out_dir):
    """herdr agent start의 `--` 뒤에 붙일 인자 목록. Codex가 상태 폴더에서 쓸 수 있는 곳은 결과 폴더뿐이다."""
    if result["provider"] == "claude":
        return ["--model", result["model"], "--effort", result["effort"]]
    if result["provider"] != "codex":
        return []
    args = (["-m", result["model"]] if result["model"] else []) + [
        "-c", f'model_reasoning_effort="{result["effort"]}"', "-s", "workspace-write"]
    if kind == "ship":   # worktree 커밋이 승인 요청으로 넘어간다. 자동 검토에 맡긴다
        return args + ["--approve-for-me", "--add-dir", out_dir]
    if kind == "run":
        return args + ["-a", "on-request", "--add-dir", out_dir]
    return args + ["-a", "on-request", "-C", out_dir]  # scout: 프로젝트는 읽기만, 쓰기는 결과 폴더만


def render(result, args, preview):
    lines = []
    if result["provider"] is None:
        lines.append("보낼 곳: 없음. 띄우지 않는다")
    else:
        model = result["model"] or "설정의 기본 모델"
        lines.append(f"보낼 곳: {result['provider']} · {model} · effort {result['effort']}")
        lines.append(f"brief의 model: {result['provider']} {model} {result['effort']}")
        lines.append(f"띄울 때 붙일 인자: {shlex.join(args)}" + (" (미리보기: --task <id>를 줘야 실제 경로가 나온다)" if preview else ""))
        if result["provider"] == "codex":
            lines.append("Codex 결과 자리: 인자에 든 결과 폴더(tasks/<id>/out). 띄우기 전에 만들고, 끝나면 그 안의 result.md를 tasks/<id>/로 옮긴다")
        if result["how"] == "subagent":
            lines.append("띄우는 방식: 호스트의 Claude subagent만. Claude CLI가 없어 herdr 세션으로는 못 띄운다. "
                         "호스트가 Claude가 아니면 --without claude로 다시 돌린다")
    lines.append("이유: " + " → ".join(result["why"]))
    lines.append("한도: " + " · ".join(f"{NAME[k]} {WORD[result['state'][k]]}" for k in NAME))
    yes = {True: "예. ", False: "아니오. ", None: ""}[result["spawn"]]
    lines.append(f"띄워도 되나: {yes}{result['spawn_why']}")
    if result["reset"]:
        what = "Fable 리셋권" if result["reset"] == "fable" else "주간 리셋권"
        lines.append(f"리셋권: {what}을 쓸지 사용자에게 묻는다. 쓰지 않고 묻기만 한다. 되돌릴 수 없다")
    else:
        lines.append("리셋권: 묻지 않는다")
    return "\n".join(lines)


def temp_roots():
    """Codex 샌드박스가 늘 쓰기를 여는 임시 폴더들. 파일을 만들어 보지 않고 이름만 모은다."""
    found = ["/tmp", "/var/tmp", os.environ.get("TMPDIR")]
    try:
        found.append(os.confstr("CS_DARWIN_USER_TEMP_DIR"))
    except (AttributeError, ValueError, OSError):
        pass
    return [p for p in found if p]


def inside(path, root):
    """path가 root 안인가(같은 곳 포함). 링크와, 대소문자를 가리지 않는 파일 시스템의 다른 표기까지 본다."""
    path, root = os.path.realpath(path), os.path.realpath(root)
    if path == root or path.startswith(root.rstrip(os.sep) + os.sep):
        return True
    while os.path.exists(root):
        try:
            if os.path.exists(path) and os.path.samefile(path, root):
                return True
        except OSError:
            pass
        if os.path.dirname(path) == path:
            break
        path = os.path.dirname(path)
    return False


def codex_can_write(brief_dir, workspace):
    """brief가 든 폴더가 Codex 작업자의 쓰기 범위(결과 폴더·작업 공간·임시 폴더) 안인가. → 까닭 | None."""
    roots = [(os.path.join(brief_dir, "out"), "결과 폴더(링크)")] + ([(workspace, "작업 공간")] if workspace else [])
    roots += [(root, "임시 폴더") for root in temp_roots()]
    for root, name in roots:
        if inside(brief_dir, root):
            return f"상태 폴더가 {name} 안에 있어 Codex 작업자가 brief를 쓸 수 있다. Claude로 보내거나(--without codex) 상태 폴더를 옮긴다"
    return None


def fresh(at, now=None):
    """usage.py가 적은 시각이 있으면 방금 읽은 값인지 본다. 묵은 사용량과 메모리로 띄우지 않는다. → 읽은 뒤 지난 시간."""
    if at is None:
        return 0.0
    try:
        seen = dt.datetime.fromisoformat(at)
        now = dt.datetime.fromisoformat(now) if now else dt.datetime.now(dt.timezone.utc)
        seen, now = (t.astimezone() if t.tzinfo is None else t for t in (seen, now))
        minutes = (now - seen).total_seconds() / 60
    except (TypeError, ValueError):
        raise BadUsage("at이 시각이 아님") from None
    if minutes > SNAPSHOT_MAX_MIN or minutes < -5:
        raise BadUsage(f"{abs(minutes):.0f}분 {'전' if minutes > 0 else '뒤'}에 읽은 값이다. usage.py를 다시 돌린다")
    return max(minutes, 0.0) / 60


def load_json(path, what):
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text("utf-8")
        data = json.loads(text)
    except (OSError, ValueError) as err:
        sys.exit(f"route.py: {what}을(를) 읽지 못함: {type(err).__name__}")
    if not isinstance(data, dict):
        sys.exit(f"route.py: {what}이(가) JSON 객체가 아님")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="작업을 어느 공급자·모델·effort로 보낼지 정한다.")
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--level", required=True, choices=LEVELS)
    parser.add_argument("--other-eyes", action="store_true")
    parser.add_argument("--urgent", action="store_true")
    parser.add_argument("--usage")
    parser.add_argument("--without", action="append", default=[], choices=["claude", "codex"])
    parser.add_argument("--task", help="작업 id")
    parser.add_argument("--workspace", help="작업자를 띄울 작업 공간")
    parser.add_argument("--not-model", choices=["fable", "opus", "sonnet"], help="고르지 않을 Claude 별칭")
    parser.add_argument("--home", default=os.environ.get("CHIEF_OF_STAFF_HOME") or "~/.chief-of-staff", help="상태 폴더")
    parser.add_argument("--now", help="시험용 현재 시각(ISO 8601)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.other_eyes and args.kind == "ship":
        parser.error("--other-eyes는 scout와 run에만 쓴다. 독립 리뷰는 고치는 일이 아니다")

    if args.task and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.task):
        sys.exit("route.py: --task는 소문자·숫자·하이픈으로 된 작업 id여야 함")
    home = Path(args.home).expanduser().absolute()  # Codex 인자의 경로는 어디서 띄워도 같아야 한다
    usage = load_json(args.usage, "사용량") if args.usage else {}
    config = load_json(home / "routing.json", "routing.json") if (home / "routing.json").is_file() else {}
    try:
        elapsed = fresh(usage.get("at"), args.now)
        result = decide(args.kind, args.level, usage, args.other_eyes, args.urgent, args.without, elapsed, args.not_model)
    except BadUsage as err:
        sys.exit(f"route.py: 사용량을 읽지 못함: {err}")
    if result["provider"] == "codex":
        model = config.get("codex_review_model" if result["role"] == "review" else "codex_model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            sys.exit("route.py: routing.json의 모델 이름이 글자가 아님")
        result["model"] = model
        blocked = codex_can_write(str(home / "tasks" / (args.task or "")), None if args.kind == "scout" else args.workspace)
        if not blocked and args.task and args.kind != "scout" and not args.workspace:
            blocked = "--workspace <작업 공간>을 줘야 Codex 작업자의 쓰기 범위에 brief가 없는지 볼 수 있다. 붙여서 다시 돌린다"
        if blocked:  # 승인 원문과 checked가 든 brief는 작업자가 쓸 수 없는 곳에 있어야 한다
            result.update(spawn=False, spawn_why=blocked, reset=None)
    out_dir = str(home / "tasks" / args.task / "out") if args.task else "<상태>/tasks/<id>/out"
    launch_args = launch(result, args.kind, out_dir)
    preview = result["provider"] == "codex" and not args.task
    if args.json:
        print(json.dumps({**result, "launch": launch_args, "preview": preview}, ensure_ascii=False))
    else:
        print(render(result, launch_args, preview))
    return 0


if __name__ == "__main__":
    sys.exit(main())
