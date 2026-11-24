#!/usr/bin/env python3
"""디스크를 차지하는 큰 폴더와 큰 파일을 한 번 걸어서 표로 낸다. macOS용. 읽기만 한다(삭제 코드 없음).

  scan.py                    홈과 /Library
  scan.py <경로> [<경로>…]   그 경로만 (삭제 전 확인, /Applications 추가 등)
  scan.py --free             남은 용량만

- 실제로 차지한 블록을 센다. 내려받지 않은 iCloud 파일은 0에 가깝고, 하드 링크는 한 번만 센다.
- 심볼릭 링크와 다른 볼륨은 따라가지 않는다. /, /System, /Volumes는 받지 않는다.
- 경로는 셸에 붙여 넣을 수 있게 따옴표를 붙여 낸다(공백·작은따옴표 포함).
"""
import argparse
import os
import shlex
import shutil
import sys
import time


class Scan:
    def __init__(self, depth, min_dir, min_file):
        self.depth, self.min_dir, self.min_file = depth, min_dir, min_file
        self.dirs, self.files, self.denied, self.seen = [], [], [], set()

    def add_file(self, path, st):
        if st.st_nlink > 1:
            if (st.st_dev, st.st_ino) in self.seen:
                return 0, 0
            self.seen.add((st.st_dev, st.st_ino))
        size = st.st_blocks * 512
        if size >= self.min_file:
            self.files.append((size, st.st_mtime, path))
        return size, st.st_mtime

    def walk(self, path, dev, level=0):
        """(크기, 가장 최근 수정 시각). level 0이 시작 폴더다."""
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
            if e.is_dir(follow_symlinks=False):
                size, when = self.walk(e.path, dev, level + 1) if st.st_dev == dev else (0, 0)
            else:
                size, when = self.add_file(e.path, st)
            total, newest = total + size, max(newest, when)
        if level == 0 or (level <= self.depth and total >= self.min_dir):
            self.dirs.append((total, newest, path))
        return total, newest


def human(n):
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.2f} MB"


def table(rows, top):
    print("| 크기 | 마지막 수정 | 경로 |\n|---|---|---|")
    for size, when, path in sorted(rows, key=lambda r: -r[0])[:top]:
        day = time.strftime("%Y-%m-%d", time.localtime(when)) if when else "?"
        text = shlex.quote(path).replace("|", "\\|").replace("\n", "\\n")
        print(f"| {human(size)} | {day} | {text} |")


def main(argv):
    ap = argparse.ArgumentParser(description="큰 폴더와 큰 파일을 표로 낸다(읽기만).")
    ap.add_argument("paths", nargs="*", help="기본: 홈, /Library")
    ap.add_argument("--free", action="store_true", help="남은 용량만 낸다")
    ap.add_argument("--depth", type=int, default=4, help="폴더를 몇 단계까지 보일지 (기본 4)")
    ap.add_argument("--min-dir-mb", type=float, default=1000, help="이보다 작은 폴더는 줄인다 (기본 1000)")
    ap.add_argument("--min-file-mb", type=float, default=500, help="이보다 작은 파일은 줄인다 (기본 500)")
    ap.add_argument("--top", type=int, default=50)
    a = ap.parse_args(argv)
    home = os.path.expanduser("~")
    paths = [os.path.abspath(os.path.expanduser(p)) for p in a.paths] or [home, "/Library"]
    for p in paths:
        real = os.path.realpath(p)
        if real == "/" or real.lower().split("/")[1] in ("system", "volumes"):
            ap.error(f"{p}: /, /System, /Volumes는 스캔하지 않는다")
        if not os.path.lexists(p):
            ap.error(f"{p}: 없는 경로다")
    use = shutil.disk_usage(home)
    print(f"디스크: 전체 {human(use.total)} / 사용 {human(use.used)} / 여유 {human(use.free)} ({time.strftime('%Y-%m-%d %H:%M')})")
    if a.free:
        return 0
    s = Scan(a.depth, a.min_dir_mb * 1e6, a.min_file_mb * 1e6)
    for p in paths:
        st = os.lstat(p)
        if os.path.isdir(p) and not os.path.islink(p):
            s.walk(p, st.st_dev)
        else:
            s.dirs.append((st.st_blocks * 512, st.st_mtime, p))
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
