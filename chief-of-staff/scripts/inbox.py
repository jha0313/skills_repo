#!/usr/bin/env python3
"""보고판. 상태 폴더를 읽어 누가 움직일 차례인지 나누고, 지금 볼 것 3개를 고른다.

읽기만 한다. 파일을 쓰거나 명령을 실행하거나 네트워크를 쓰지 않는다.
정렬: 사람 차례 → 마감(7일 이내, 지난 것 먼저) → 막힌 것 → focus.md 우선순위.
"""
import argparse
import datetime
import hashlib
import os
import re
import sys
from pathlib import Path

RESULTS = ("done", "needs-decision", "needs-human", "blocked", "failed")
KINDS = ("ship", "run", "scout")
KEYS = ("RESULT", "SUMMARY", "EVIDENCE", "FILES", "ARTIFACTS", "PR", "DECISION", "HUMAN", "FOLLOWUPS")
WINDOW = 7          # 마감을 앞당겨 보는 날 수
FAR = 10**6
DONE_SHOWN = 10


def read(path):
    """없으면 None. 폴더이거나 읽을 수 없으면 빈 글로 보고 '깨짐'으로 다룬다."""
    try:
        text = path.read_bytes().decode("utf-8-sig", "replace")
    except FileNotFoundError:
        return None
    except OSError:
        return ""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.S)


def short(text, limit=160):
    text = " ".join("".join(c if c.isprintable() else " " for c in text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def days_until(text, today):
    """YYYY-MM-DD로 시작하면 남은 날 수, 아니면 None."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})\b", text)
    try:
        return (datetime.date.fromisoformat(m[1]) - today).days if m else None
    except ValueError:
        return None


def due_label(days):
    return f"지남 {-days}일" if days < 0 else "오늘" if days == 0 else f"D-{days}"


def read_focus(text, today, warn):
    order, deadlines = {}, []
    for number, line in enumerate((text or "").splitlines(), 1):
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
        if not line or line.startswith("#"):
            continue
        dated = re.match(r"\d{4}-\d{2}-\d{2}\s+([\w.-]+)\s*:\s*(.+)", line)
        days = days_until(line, today)
        name = re.match(r"([\w.-]+)\s*(?::|$)", line)
        if dated and days is not None:
            deadlines.append((days, dated[1], dated[2]))
        elif name and not re.match(r"\d{4}-", line):
            order.setdefault(name[1], len(order))
        else:
            warn.append(f"focus.md {number}번째 줄을 읽지 못함: {short(line, 60)}")
    return order, deadlines


def read_brief(text):
    head = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        m = re.match(r"([a-z]+):[ \t]*(.*)$", line)
        if m:
            head[m[1]] = m[2].strip()
    return head


def read_result(text):
    found, key = {}, None
    for line in text.splitlines():
        m = re.match(r"([A-Z]+):[ \t]*(.*)$", line)
        if m and m[1] in KEYS:
            key = m[1]
            found.setdefault(key, []).append(m[2])
        elif key and not line.startswith("```"):
            found[key].append(line)
    values = {v.strip().lower() for v in re.findall(r"^RESULT:(.*)$", text, re.M)}
    out = {k: "\n".join(v).strip() for k, v in found.items()}
    out["RESULT"] = values.pop() if len(values) == 1 else ""
    if out["RESULT"] not in RESULTS:
        out["RESULT"] = "broken"
    return out


def load_task(folder, today, warn):
    """(그룹, 사람 차례인가, 막혔나, 한 줄 설명)을 정한다."""
    task = {"id": short(folder.name, 60), "project": "?", "kind": "?", "due": None, "human": False, "stuck": False}

    def put(group, note, human=False, stuck=False):
        task.update(group=group, note=note, human=human, stuck=stuck)
        return task

    text = read(folder / "brief.md")
    if text is None:
        return put("내 차례", "brief.md가 없음. 무슨 작업인지 확인 필요", stuck=True)
    head = read_brief(text)
    task["project"], task["kind"] = short(head.get("project"), 40) or "?", short(head.get("kind"), 20) or "?"
    if task["kind"] not in KINDS:
        warn.append(f"{task['id']}: kind가 ship·run·scout가 아님 ({task['kind']})")
    if head.get("due"):
        task["due"] = days_until(head["due"], today)
        if task["due"] is None:
            warn.append(f"{task['id']}: due를 읽지 못함 ({short(head['due'], 40)})")

    body = read(folder / "result.md")
    result = read_result(body) if body is not None else {}
    state = result.get("RESULT")
    mark = ""
    if state == "done":
        mark = hashlib.sha256((folder / "result.md").read_bytes()).hexdigest()[:8]
    checked = head.get("checked", "")
    fresh = bool(mark) and checked.startswith(mark)

    if head.get("closed"):
        note = short(head["closed"])
        return put("끝남", note + (" (확인 기록 없음)" if state == "done" and not fresh else ""))
    if head.get("ask"):
        return put("내 차례", "답을 기다림: " + short(head["ask"]), human=True)
    if state == "broken":
        return put("내 차례", "result.md의 RESULT를 읽지 못함. 완료로 치지 않음", stuck=True)
    if state in ("needs-human", "needs-decision"):
        why = result.get("HUMAN" if state == "needs-human" else "DECISION") or result.get("SUMMARY")
        return put("내 차례", f"{state}: {short(why) or '이유가 비어 있음'}", human=True)
    if state in ("blocked", "failed"):
        return put("내 차례", f"{state}: {short(result.get('SUMMARY')) or '이유가 비어 있음'}", stuck=True)
    if state == "done" and not result.get("EVIDENCE"):
        return put("내 차례", "done이라는데 EVIDENCE가 비어 있음. 완료로 치지 않음", stuck=True)
    if state == "done":
        label = "확인됨" if fresh else f"{'확인 뒤 결과가 바뀜' if checked else '확인 전(작업자의 말)'}, 지문 {mark}"
        return put("읽을 것", f"{label}: {short(result.get('SUMMARY')) or '요약 없음'}")
    if body is None and (folder / "out" / "result.md").is_file():
        return put("내 차례", "out/result.md가 있음. 결과를 작업 폴더로 옮기고 다시 본다", stuck=True)
    if head.get("started"):
        where = f", 작업자 {short(head['worker'], 60)}" if head.get("worker") else ""
        return put("작업 중", f"시작 {short(head['started'], 30)}, 결과 없음{where}")
    return put("작업 중", "시작 전")


def line_of(item):
    due = f" · {due_label(item['due'])}" if item["due"] is not None else ""
    where = f"{item['project']}/{item['kind']}" if item["kind"] != "마감" else item["project"]
    return f"{item['id']} · {where}{due} · {item['note']}"


def board(home, today):
    warn, tasks = [], []
    order, deadlines = read_focus(read(home / "focus.md"), today, warn)
    root = home / "tasks"
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if folder.is_dir() and not folder.name.startswith("."):
            tasks.append(load_task(folder, today, warn))
    open_tasks = [t for t in tasks if t["group"] != "끝남"]

    dated = []
    for days, project, what in sorted(deadlines):
        mine = [t for t in open_tasks if t["project"] == project]
        if days <= WINDOW:  # 같은 날 작업이 있어도 그 마감을 맡았다는 뜻은 아니다. 이름을 숨기지 않는다
            note = f"{short(what)} ({f'열린 작업 {len(mine)}개' if mine else '맡긴 작업 없음'})"
            dated.append({"id": "마감", "project": project, "kind": "마감", "due": days, "human": False,
                          "stuck": False, "group": "마감", "note": note})

    def key(item):
        due = FAR if item["due"] is None else item["due"]
        return (not item["human"], due if due <= WINDOW else FAR, not item["stuck"],
                order.get(item["project"], FAR), due, item["id"])

    soon = [t for t in open_tasks if t["group"] != "작업 중" or (t["due"] is not None and t["due"] <= WINDOW)]
    ranked = sorted(soon + dated, key=key)
    top, groups = ranked[:3], {}
    for name in ("내 차례", "읽을 것", "작업 중", "마감", "끝남"):
        groups[name] = sorted((i for i in tasks + dated if i["group"] == name), key=key)

    out = [f"상태 폴더: {home} · 오늘 {today}"]
    if order:
        out.append("우선순위: " + " > ".join(order))
    out.append(f"== 지금 볼 것 ({len(top)})")
    out += [f"  {n}. {line_of(i)}" for n, i in enumerate(top, 1)] or ["  없음"]
    rest = [(name, sum(all(i is not t for t in top) for i in items)) for name, items in groups.items()]
    out.append("나머지: " + " · ".join(f"{name} {count}" for name, count in rest if name != "마감" or count))
    for name, items in groups.items():
        if name == "마감" and not items:
            continue
        out.append(f"== {name} ({len(items)})")
        shown = items[:DONE_SHOWN] if name == "끝남" else items
        out += [f"  - {line_of(i)}" for i in shown]
        if len(shown) < len(items):
            out.append(f"  외 {len(items) - len(shown)}개")
    if warn:
        out += [f"== 경고 ({len(warn)})"] + [f"  - {w}" for w in warn]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="비서실장 보고판(읽기 전용)")
    parser.add_argument("--home", default=os.environ.get("CHIEF_OF_STAFF_HOME") or "~/.chief-of-staff", help="상태 폴더")
    parser.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today(), help="YYYY-MM-DD")
    args = parser.parse_args()
    home = Path(args.home).expanduser()
    if not home.is_dir():
        print(f"상태 폴더가 없음: {home} (빈 보고판이 아니다. CHIEF_OF_STAFF_HOME을 확인할 것)", file=sys.stderr)
        return 2
    print(board(home, args.today))
    return 0


if __name__ == "__main__":
    sys.exit(main())
