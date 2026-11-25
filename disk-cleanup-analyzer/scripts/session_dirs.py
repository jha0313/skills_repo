#!/usr/bin/env python3
"""Claude Code 세션 작업 폴더를 나열하고 KEEP / REVIEW / ASK로 판정한다. macOS 전용. 읽기만 한다(삭제 코드 없음).

대상: /private/tmp/claude-<uid>/<프로젝트>/<세션 id>/

  KEEP    정리 후보가 아니다. 열려 있음 / 최근 활동 / 대화 기록 없음 / 확인 실패 중 하나라도 걸리면 KEEP이다.
  REVIEW  오래 쉬었지만 원본일 수 있는 파일이 있다. 지우지 말고 먼저 옮길지 묻는다.
  ASK     오래 쉬었고 원본으로 보이는 파일도 없다. "지워도 됨"이 아니라 "폴더별로 물어볼 수 있음"이다.

열어 둔 채 쉬는 세션은 파일을 잡지 않고 프로세스 인자에 id도 없을 수 있다. 그래서 세 가지를 함께 본다.
  1) claude가 들어간 프로세스의 작업 디렉터리와 인자 속 세션 id. 그 디렉터리의 세션은 모두 열린 것으로 본다.
  2) herdr가 깔려 있으면 패널의 디렉터리(선택).
  3) 대화 기록(~/.claude/projects)과 폴더 안 파일의 마지막 수정 시각.
ps·lsof·herdr가 실패해 확인하지 못하면 전부 KEEP으로 둔다.

사용: session_dirs.py [--days N] [--all] [--no-herdr] [--root 폴더] [--projects 폴더]
"""
import argparse
import glob
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
CACHE_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".cache"}   # 이 안의 파일도 세되 목록 뒤에 둔다
JUNK_EXT = {".log", ".output", ".out", ".tmp", ".temp", ".pyc", ".o", ".pid", ".lock", ".sock"}
SMALL = 10e6


def run(*cmd, ok=(0,)):
    """명령 출력. 실행하지 못했거나 종료 코드가 ok에 없으면 None(출력이 일부만 나왔을 수 있다)."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode in ok else None


def unescape(name):
    """lsof는 C 로캘에서 한글을 \\xed\\x95처럼 적는다."""
    raw = re.sub(rb"\\x([0-9a-f]{2})", lambda m: bytes([int(m[1], 16)]), name.encode())
    return raw.decode("utf-8", "replace")


def base(path):
    """경로나 프로젝트 폴더 이름을 비교용으로 바꾼다. 워크트리는 원래 저장소와 같게 본다."""
    return re.sub(r"[^A-Za-z0-9]+", "-", path).split("-claude-worktrees-")[0].rstrip("-")


def covers(cwd, proj):
    p, c = base(proj), base(cwd)
    return p == c or (len(cwd) > 150 and p.startswith(base(cwd[:150])))  # 긴 경로는 이름이 잘린다


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def from_processes():
    out = run("ps", "-xwwo", "pid=,command=")
    if not out or not out.strip():
        return set(), set(), ["ps가 실패함"]
    ids, pids = set(), []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if pid.isdigit() and "claude" in cmd.lower():
            ids.update(re.findall(UUID, cmd))
            pids.append(int(pid))
    cwd_of, pid = {}, None
    if pids:
        # lsof는 그사이 끝난 pid가 있으면 1로 끝난다. 빠진 것은 아래 lost에서 pid마다 본다.
        out = run("lsof", "-a", "-d", "cwd", "-Fpn", "-p", ",".join(map(str, pids)), ok=(0, 1))
        for line in (out or "").splitlines():
            if line[:1] == "p":
                pid = int(line[1:])
            elif line[:1] == "n":
                cwd_of[pid] = unescape(line[1:])
    lost = [p for p in pids if p not in cwd_of and p != os.getpid() and alive(p)]
    return ids, set(cwd_of.values()), [f"claude 프로세스 {len(lost)}개의 작업 디렉터리를 모름"] if lost else []


def from_herdr():
    try:
        agents = json.loads(run("herdr", "agent", "list") or "")["result"]["agents"]
        cwds = {a["cwd"] for a in agents} | {a["foreground_cwd"] for a in agents if a.get("foreground_cwd")}
        return cwds | {os.path.realpath(c) for c in cwds}, []
    except (ValueError, KeyError, TypeError):
        return set(), ["herdr 패널 목록을 읽지 못함(herdr를 쓰지 않으면 --no-herdr)"]


def title(path):
    """대화 기록에서 제목 필드만 뽑는다."""
    found = ""
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if 'Title":"' in line:
                    for t in re.findall(r'"(?:aiTitle|customTitle)":"((?:[^"\\]|\\.)*)"', line):
                        found = json.loads(f'"{t}"')
    except (OSError, ValueError):
        pass
    return found


def look(top):
    """(크기, 가장 최근 수정 시각, 원본일 수 있는 파일, 읽지 못한 곳)"""
    size, newest, src, cached, bad = 0, 0, [], [], []
    for path, dirs, files in os.walk(top, onerror=bad.append):
        dirs.sort()
        rel = os.path.relpath(path, top)
        parts = set(rel.split(os.sep))
        found = cached if CACHE_DIRS & parts else src
        if ".git" in dirs:
            found.append(os.path.normpath(os.path.join(rel, ".git")))
        for name in sorted(files):
            try:
                st = os.lstat(os.path.join(path, name))
            except OSError as e:
                bad.append(e)
                continue
            size += st.st_blocks * 512
            newest = max(newest, st.st_mtime)
            ext = os.path.splitext(name)[1].lower()
            if stat.S_ISREG(st.st_mode) and st.st_size and ".git" not in parts and ext not in JUNK_EXT and name != ".DS_Store":
                found.append(os.path.normpath(os.path.join(rel, name)))
    return size, newest, src + cached, bad


def cell(text):
    return text.replace("|", "\\|").replace("\n", "\\n") or "-"


def main(argv):
    ap = argparse.ArgumentParser(description="세션 작업 폴더를 KEEP/REVIEW/ASK로 판정한다(읽기만).")
    ap.add_argument("--days", type=float, default=7, help="이 일수 안에 바뀌었으면 KEEP (기본이자 최소 7)")
    ap.add_argument("--all", action="store_true", help="10 MB 미만 KEEP도 모두 보인다")
    ap.add_argument("--no-herdr", action="store_true", help="herdr가 깔려 있어도 보지 않는다")
    ap.add_argument("--root", help="작업 폴더 뿌리 (기본 /private/tmp/claude-<uid>)")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"), help="대화 기록 폴더")
    a = ap.parse_args(argv)
    if not a.days >= 7:
        ap.error("--days는 7 이상이어야 한다(늘릴 수만 있다)")
    if sys.platform != "darwin" and not a.root:
        ap.error("macOS 전용이다")
    root = a.root or f"/private/tmp/claude-{os.getuid()}"
    ids, cwds, unknown = from_processes()
    note = "herdr 없음"
    if a.no_herdr:
        note = "herdr 보지 않음"
    elif shutil.which("herdr"):
        more, bad = from_herdr()
        cwds, unknown, note = cwds | more, unknown + bad, "herdr 패널 포함"
    now, rows = time.time(), []
    for d in sorted(glob.glob(os.path.join(glob.escape(root), "*", "*"))):
        proj, sid = d.split(os.sep)[-2:]
        if not os.path.isdir(d) or not re.fullmatch(UUID, sid):
            continue
        logs = glob.glob(os.path.join(glob.escape(a.projects), "*", sid + ".jsonl"))
        size, newest, src, bad = look(d)
        last = max([newest] + [os.path.getmtime(f) for f in logs])
        why = []
        if unknown:
            why.append("확인 실패")
        if sid in ids or any(covers(c, proj) for c in cwds):
            why.append("열려 있음")
        if last and now - last < a.days * 86400:
            why.append("최근 활동")
        if not logs:
            why.append("대화 기록 없음")
        if bad:
            why.append("읽지 못한 파일 있음")
        verdict = "KEEP" if why else "REVIEW" if src else "ASK"
        rows.append((verdict, size, last, title(logs[0]) if logs else "", why, src, d))

    print(f"# 세션 작업 폴더 ({root})\n")
    print(f"열린 세션 기준: claude 프로세스 · {note} · 최근 {a.days:g}일")
    for u in unknown:
        print(f"**확인 실패 → 전부 KEEP**: {u}")
    if not rows:
        print("세션 작업 폴더가 없다.")
        return 0
    print("\n| 판정 | 크기 | 마지막 활동 | 세션 제목 | 이유 | 원본일 수 있는 파일 | 경로 |\n|---|---|---|---|---|---|---|")
    order = ["KEEP", "REVIEW", "ASK"]
    hidden = 0
    for v, size, last, name, why, src, d in sorted(rows, key=lambda r: (order.index(r[0]), -r[1])):
        if v == "KEEP" and size < SMALL and not a.all:
            hidden += 1
            continue
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "?"
        files = f"{len(src)}개 (예: {', '.join(src[:3])})" if src else "0개"
        print(f"| {v} | {size / 1e6:.1f} MB | {when} | {cell(name)} | {', '.join(why) or '-'} | {cell(files)} | `{cell(d)}` |")
    if hidden:
        print(f"\n10 MB 미만 KEEP {hidden}개는 줄였다(--all로 모두 보기).")
    ask = [r[1] for r in rows if r[0] == "ASK"]
    print(f"\nASK {len(ask)}개, 합계 {sum(ask) / 1e9:.2f} GB. ASK는 '지워도 됨'이 아니다. 폴더마다 묻고, 지우기 직전에 다시 돌린다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
