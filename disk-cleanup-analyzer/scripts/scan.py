#!/usr/bin/env python3
"""디스크를 차지하는 큰 폴더와 큰 파일을 한 번 걸어서 표로 낸다. macOS용. 읽기만 한다(삭제 코드 없음).

  scan.py                    홈과 /Library
  scan.py <경로> [<경로>…]   그 경로만 (/Applications 추가 등)
  scan.py --free             남은 용량만
  scan.py --record <경로>…   승인 기록을 JSON으로 낸다(원래 경로·바이트·mtime_ns·하위 목록 해시)
  scan.py --check <기록>     기록의 경로를 다시 재서 대조한다. 종료 코드: 0 같음 / 1 달라짐 / 2 확인 못 함

- 실제로 차지한 블록을 센다. 내려받지 않은 iCloud 파일은 0에 가깝고, 하드 링크는 한 번만 센다.
- 심볼릭 링크와 다른 볼륨은 따라가지 않는다. /, /System, /Volumes는 받지 않는다.
- 경로는 셸에 붙여 넣을 수 있게 따옴표를 붙여 낸다(공백·작은따옴표·개행 포함).
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import sys
import time


class Scan:
    items = None   # 리스트면 걸은 항목의 (경로, 종류, 크기, mtime_ns)를 모은다(승인 기록용)

    def __init__(self, depth, min_dir, min_file):
        self.depth, self.min_dir, self.min_file = depth, min_dir, min_file
        self.dirs, self.files, self.denied, self.seen = [], [], [], set()
        self.volumes = []   # 걷지 않은 다른 볼륨

    def add_file(self, path, st):
        if st.st_nlink > 1:
            if (st.st_dev, st.st_ino) in self.seen:
                return 0, 0
            self.seen.add((st.st_dev, st.st_ino))
        size = st.st_blocks * 512
        if size >= self.min_file:
            self.files.append((size, st.st_mtime_ns, path))
        return size, st.st_mtime_ns

    def walk(self, path, dev, level=0):
        """(크기, 가장 최근 수정 시각 ns). level 0이 시작 폴더다."""
        total, newest = 0, 0
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except OSError:
            self.denied.append(path)
            return 0, 0
        for e in entries:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                self.denied.append(e.path)
                continue
            self.note(e.path, st)
            if st.st_dev != dev:
                self.volumes.append(e.path)
            if e.is_dir(follow_symlinks=False):
                size, when = self.walk(e.path, dev, level + 1) if st.st_dev == dev else (0, 0)
            else:
                size, when = self.add_file(e.path, st)
            total, newest = total + size, max(newest, when)
        if level == 0 or (level <= self.depth and total >= self.min_dir):
            self.dirs.append((total, newest, path))
        return total, newest

    def note(self, path, st):
        if self.items is not None:
            self.items.append((path, stat.S_IFMT(st.st_mode), st.st_size, st.st_mtime_ns))

    def measure(self, path):
        st = os.lstat(path)
        self.note(path, st)
        if os.path.isdir(path) and not os.path.islink(path):
            return self.walk(path, st.st_dev)
        self.dirs.append((st.st_blocks * 512, st.st_mtime_ns, path))
        return st.st_blocks * 512, st.st_mtime_ns


def human(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.2f} MB"


def shown(size, when):
    return f"{human(size)}, {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(when / 1e9)) if when else '?'}"


def shell(path):
    """셸(zsh·bash)에 그대로 넣으면 원래 경로가 되는 글. 표와 줄을 깨는 글자는 $'\\x0a'처럼 적는다."""
    if not re.search(r"[\x00-\x1f\x7f|]", path):
        return shlex.quote(path)
    return "$'" + re.sub(r"[\x00-\x1f\x7f|'\\]", lambda m: f"\\x{ord(m[0]):02x}", path) + "'"


def table(rows, top):
    print("| 크기 | 마지막 수정 | 경로 |\n|---|---|---|")
    rows = sorted(rows, key=lambda r: -r[0])
    for size, when, path in rows[:top]:
        day = time.strftime("%Y-%m-%d", time.localtime(when / 1e9)) if when else "?"
        print(f"| {human(size)} | {day} | {shell(path)} |")
    if len(rows) > len(rows[:top]):
        print(f"\n{len(rows) - len(rows[:top])}개는 줄였다(--top을 빼면 모두 낸다).")


def fingerprint(path):
    """((크기, 최근 수정 ns, 하위 목록 해시), 확인하지 못한 곳). 해시는 경로 순으로 정렬한 (상대 경로, 종류, 크기, mtime_ns) 목록의 것이다."""
    s = Scan(0, float("inf"), float("inf"))
    s.items = []
    size, when = s.measure(path)
    h = hashlib.sha256()
    for p, *rest in sorted(s.items):
        h.update(repr((p[len(path):], *rest)).encode())
    return (size, when, h.hexdigest()), [("읽지 못함", p) for p in s.denied] + [("다른 볼륨", p) for p in s.volumes]


def check(records):
    """기록과 지금이 모두 같으면 0, 다른 것이 있으면 1, 확인하지 못한 곳이 있으면 2."""
    code = 0
    for path, old in records:
        now, unsure = fingerprint(path)
        result = 2 if unsure else int(now != old)
        code = max(code, result)
        print(f"{['같음', '달라짐', '확인 못 함'][result]}: {shell(path)}")
        print(f"  기록 {shown(*old[:2])} / 지금 {shown(*now[:2])}" + (", 하위 목록 다름" if result == 1 and now[2] != old[2] else ""))
        for why, p in unsure:
            print(f"  {why}: {shell(p)}")
    return code


def main(argv):
    ap = argparse.ArgumentParser(description="큰 폴더와 큰 파일을 표로 낸다(읽기만).")
    ap.add_argument("paths", nargs="*", help="기본: 홈, /Library")
    ap.add_argument("--free", action="store_true", help="남은 용량만 낸다")
    ap.add_argument("--record", action="store_true", help="그 경로의 승인 기록(JSON)을 낸다")
    ap.add_argument("--check", metavar="기록", help="승인 기록과 지금을 대조한다")
    ap.add_argument("--depth", type=int, default=4, help="폴더를 몇 단계까지 보일지 (기본 4)")
    ap.add_argument("--min-dir-mb", type=float, default=1000, help="이보다 작은 폴더는 줄인다 (기본 1000)")
    ap.add_argument("--min-file-mb", type=float, default=500, help="이보다 작은 파일은 줄인다 (기본 500)")
    ap.add_argument("--top", type=int, help="표마다 이 줄 수까지만 (기본: 모두)")
    a = ap.parse_args(argv)
    home = os.path.expanduser("~")
    checking = a.check is not None
    if a.record and not a.paths or checking and (a.paths or a.record or a.free):
        ap.error("--record에는 경로를, --check에는 기록 파일 하나만 준다")
    use = shutil.disk_usage(home)
    free = f"디스크: 전체 {human(use.total)} / 사용 {human(use.used)} / 여유 {human(use.free)} ({time.strftime('%Y-%m-%d %H:%M')})"
    if a.free:
        print(free)
        return 0
    records = []
    if checking:
        try:
            with open(a.check, encoding="utf-8") as f:
                records = [(r["path"], (r["bytes"], r["mtime_ns"], r["list"])) for r in json.load(f)]
        except (OSError, ValueError, KeyError, TypeError) as e:
            ap.error(f"{a.check}: 기록을 읽지 못했다({e})")
        if not records:
            ap.error(f"{a.check}: 기록이 비었다")
    paths = [os.path.abspath(os.path.expanduser(p)) for p in a.paths] or [r[0] for r in records] or [home, "/Library"]
    for p in paths:
        real = os.path.realpath(p)
        if real == "/" or real.lower().split("/")[1] in ("system", "volumes"):
            ap.error(f"{p}: /, /System, /Volumes는 스캔하지 않는다")
        if not os.path.lexists(p):
            ap.error(f"{p}: 없는 경로다")
    if checking:
        return check(records)
    if a.record:
        got = [(p, *fingerprint(p)) for p in paths]
        for p, _, unsure in got:
            if unsure:
                ap.error(f"{p}: 확인하지 못한 곳이 있어 기록하지 않는다\n" + "\n".join(f"  {why}: {shell(x)}" for why, x in unsure))
        print(json.dumps([dict(path=p, bytes=b, mtime_ns=t, list=h, shown=shown(b, t)) for p, (b, t, h), _ in got],
                         ensure_ascii=False, indent=1))
        return 0
    print(free)
    s = Scan(a.depth, a.min_dir_mb * 1e6, a.min_file_mb * 1e6)
    for p in paths:
        s.measure(p)
    print(f"\n## 큰 폴더 ({a.min_dir_mb:g} MB 이상, {a.depth}단계까지. 위 폴더 크기에 아래 폴더가 들어 있다)")
    table(s.dirs, a.top)
    print(f"\n## 큰 파일 ({a.min_file_mb:g} MB 이상)")
    table(s.files, a.top)
    if s.denied:
        print(f"\n## 읽지 못한 곳 {len(s.denied)}개 (크기에 빠졌다)")
        for p in s.denied[:10]:
            print(f"- {shlex.quote(p)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
