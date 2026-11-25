#!/usr/bin/env python3
"""session_dirs.py · scan.py 테스트. 임시 폴더와 가짜 ps·lsof·herdr만 쓴다(실제 홈은 보지 않는다).

사용: python3 tests/run_tests.py
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS = os.path.join(SKILL, "scripts", "session_dirs.py")
SCAN = os.path.join(SKILL, "scripts", "scan.py")
A = "aaaaaaaa-0000-4000-8000-000000000001"
B = "bbbbbbbb-0000-4000-8000-000000000002"
C = "cccccccc-0000-4000-8000-000000000003"


def read(*parts):
    with open(os.path.join(SKILL, *parts), encoding="utf-8") as f:
        return f.read()


class Temp(unittest.TestCase):
    prefix = "dca-"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix=self.prefix)
        self.addCleanup(tmp.cleanup)
        self.tmp = os.path.realpath(tmp.name)

    def write(self, path, text="x", days_old=0):
        path = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        when = time.time() - days_old * 86400
        os.utime(path, (when, when))
        return path

    def tree(self):
        return sorted((os.path.join(d, f), os.lstat(os.path.join(d, f)).st_mtime_ns)
                      for d, _, fs in os.walk(self.tmp) for f in fs)


class Sessions(Temp):
    prefix = "dca it's 한글 "   # 뿌리 폴더 자체에 공백·작은따옴표·한글

    def setUp(self):
        super().setUp()
        self.bin = tempfile.TemporaryDirectory(prefix="dcabin")
        self.addCleanup(self.bin.cleanup)
        os.makedirs(os.path.join(self.tmp, "root"))
        self.stub("ps", "    1 /sbin/launchd\n")
        self.stub("lsof", "")

    def stub(self, name, out, code=0):
        text = os.path.join(self.bin.name, name + ".txt")
        with open(text, "w", encoding="utf-8") as f:
            f.write(out)
        path = os.path.join(self.bin.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/sh\ncat '{text}'\nexit {code}\n")
        os.chmod(path, 0o755)

    def session(self, proj, sid, files=(("tasks/a.output", "log"),), log_days=30, file_days=30, name=""):
        for f, text in files:
            self.write(f"root/{proj}/{sid}/{f}", text, file_days)
        os.makedirs(os.path.join(self.tmp, "root", proj, sid), exist_ok=True)
        if log_days is not None:
            line = '{"type":"user","text":"숨길 내용"}\n' + (f'{{"customTitle":"{name}"}}\n' if name else "")
            self.write(f"projects/{proj}/{sid}.jsonl", line, log_days)

    def run_it(self, *args, code=0):
        r = subprocess.run(
            [sys.executable, "-I", SESSIONS, "--all", "--root", os.path.join(self.tmp, "root"),
             "--projects", os.path.join(self.tmp, "projects"), *args],
            capture_output=True, text=True, encoding="utf-8",
            env={"PATH": self.bin.name + ":/usr/bin:/bin", "HOME": self.tmp, "PYTHONUTF8": "1", "LC_ALL": "en_US.UTF-8"})
        self.assertEqual(r.returncode, code, r.stderr)
        return r.stdout

    def rows(self, *args):
        out = {}
        for line in self.run_it(*args).splitlines():
            m = re.match(r"\| (KEEP|REVIEW|ASK) \|", line)
            if m:
                c = [x.strip() for x in re.split(r"(?<!\\)\|", line)[1:-1]]
                proj, sid = c[6].strip("`").split("/")[-2:]
                out[(proj, sid)] = dict(verdict=c[0], title=c[3], why=c[4], files=c[5])
        return out

    def verdicts(self, *args):
        return {sid: r["verdict"] for (_, sid), r in self.rows(*args).items()}

    # 판정
    def test_ask_when_old_and_only_logs(self):
        self.session("-w-app", A)
        self.assertEqual(self.verdicts(), {A: "ASK"})

    def test_review_when_original_like_file(self):
        self.session("-w-app", A, [("scratchpad/site/index.html", "<p>")])
        r = self.rows()[("-w-app", A)]
        self.assertEqual(r["verdict"], "REVIEW")
        self.assertIn("scratchpad/site/index.html", r["files"])

    def test_unknown_or_missing_extension_is_review(self):
        for i, f in enumerate(["Makefile", "main.swift", "notes.docx", "clip.mp4", "fix.patch"]):
            with self.subTest(f):
                proj = f"-w-p{i}"
                self.session(proj, A, [(f, "data")])
                self.assertEqual(self.rows()[(proj, A)]["verdict"], "REVIEW")

    def test_git_dir_is_review(self):
        self.session("-w-app", A, [("repo/.git/HEAD", "ref")])
        self.assertEqual(self.verdicts(), {A: "REVIEW"})

    def test_logs_bytecode_and_empty_files_do_not_make_review(self):
        self.session("-w-app", A, [(".cache/run.log", "1"), ("__pycache__/x.pyc", "1"), ("empty.py", ""), (".DS_Store", "x")])
        self.assertEqual(self.verdicts(), {A: "ASK"})

    def test_original_inside_a_cache_folder_is_review(self):
        # 예전에는 상위 폴더 이름이 캐시면 그 안의 하나뿐인 원본을 세지 않았다
        for i, f in enumerate([".cache/only-copy.md", "node_modules/x/fix.patch", ".venv/src/a.py", "__pycache__/memo.txt",
                               "node_modules/x/.git/HEAD"]):
            with self.subTest(f):
                proj = f"-w-p{i}"
                self.session(proj, A, [(f, "data")])
                r = self.rows()[(proj, A)]
                self.assertEqual(r["verdict"], "REVIEW")
                self.assertIn("1개 (예: " + f.replace("/HEAD", ""), r["files"])

    def test_files_outside_cache_folders_are_shown_first(self):
        self.session("-w-app", A, [(f".cache/{i}.js", "1") for i in range(5)] + [("site/z.html", "<p>")])
        self.assertIn("6개 (예: site/z.html", self.rows()[("-w-app", A)]["files"])

    def test_recent_transcript_keeps(self):
        self.session("-w-app", A, log_days=2)
        self.session("-w-app", B, log_days=8)
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "ASK"})
        self.assertEqual(self.verdicts("--days", "30"), {A: "KEEP", B: "KEEP"})

    def test_recent_file_keeps_even_if_transcript_is_old(self):
        self.session("-w-app", A, file_days=1)
        self.assertEqual(self.rows()[("-w-app", A)]["why"], "최근 활동")

    def test_missing_transcript_keeps(self):
        self.session("-w-app", A, log_days=None)
        r = self.rows()[("-w-app", A)]
        self.assertEqual((r["verdict"], r["why"]), ("KEEP", "대화 기록 없음"))

    def test_unreadable_folder_keeps(self):
        self.session("-w-app", A, [("locked/a.output", "x")])
        locked = os.path.join(self.tmp, "root/-w-app", A, "locked")
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o700)
        if os.access(locked, os.R_OK):
            self.skipTest("root로 실행 중")
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    def test_non_session_folders_are_not_listed(self):
        self.write("root/-w-app/not-a-session/file.py")
        self.assertIn("세션 작업 폴더가 없다", self.run_it())

    # 열린 세션
    def test_idle_process_without_id_keeps_its_folder(self):
        self.session("-w-app", A)
        self.session("-w-other", B)
        self.stub("ps", "  501 claude\n")
        self.stub("lsof", "p501\nfcwd\nn/w/app\n")
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "ASK"})

    def test_id_in_arguments_keeps_that_id_and_the_whole_folder(self):
        # /clear나 fork 뒤에는 인자의 id와 실제 세션 id가 다르다
        self.session("-w-app", A)
        self.session("-elsewhere", B)
        self.session("-w-third", C)
        self.stub("ps", f"  501 claude --resume {B}\n")
        self.stub("lsof", "p501\nfcwd\nn/w/app\n")
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "KEEP", C: "ASK"})

    def test_versioned_binary_path_is_seen(self):
        self.session("-w-app", A)
        self.stub("ps", "  501 /opt/share/claude/versions/9.9.9 --print\n")
        self.stub("lsof", "p501\nfcwd\nn/w/app\n")
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    def test_worktree_and_repo_protect_each_other(self):
        self.session("-w-app--claude-worktrees-fix", A)
        self.session("-w-tool", B)
        self.stub("ps", "  501 claude\n  502 claude\n")
        self.stub("lsof", "p501\nfcwd\nn/w/app\np502\nfcwd\nn/w/tool/.claude/worktrees/x\n")
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "KEEP"})

    def test_korean_path_escaped_by_lsof(self):
        self.session("-w------app", A)   # /w/한글 앱/app 같은 이름이 -로 바뀐 폴더
        self.stub("ps", "  501 claude\n")
        self.stub("lsof", "p501\nfcwd\nn/w/\\xed\\x95\\x9c\\xea\\xb8\\x80 x/app\n")
        self.assertEqual(self.verdicts(), {A: "ASK"})   # 다른 폴더(x가 있음)는 지키지 않는다
        self.stub("lsof", "p501\nfcwd\nn/w/\\xed\\x95\\x9c\\xea\\xb8\\x80/app\n")
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    def test_very_long_path_is_matched_by_prefix(self):
        cwd = "/w/" + "a" * 260
        self.session(("-w-" + "a" * 197) + "-h4sh", A)
        self.stub("ps", "  501 claude\n")
        self.stub("lsof", f"p501\nfcwd\nn{cwd}\n")
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    # 확인하지 못하면 KEEP
    def test_ps_failure_keeps_everything(self):
        self.session("-w-app", A)
        self.stub("ps", "", code=1)
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    def test_partial_output_with_failed_exit_keeps_everything(self):
        self.session("-w-app", A)
        self.stub("ps", "    1 /sbin/launchd\n", code=1)
        self.assertEqual(self.rows()[("-w-app", A)]["why"], "확인 실패")
        self.stub("ps", "    1 /sbin/launchd\n")
        self.stub("herdr", '{"result":{"agents":[]}}', code=1)
        self.assertEqual(self.rows()[("-w-app", A)]["why"], "확인 실패")

    def test_lsof_exit_1_is_judged_per_process(self):
        # lsof는 이미 끝난 pid가 하나만 섞여도 1로 끝난다
        p = subprocess.Popen(["true"])
        p.wait()
        self.session("-w-app", A)
        self.session("-w-other", B)
        self.stub("ps", f"  {os.getpid()} claude\n  {p.pid} claude\n")
        self.stub("lsof", f"p{os.getpid()}\nfcwd\nn/w/app\n", code=1)
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "ASK"})

    def test_process_without_known_cwd_keeps_everything(self):
        self.session("-w-app", A)
        self.stub("ps", f"  {os.getpid()} claude\n")   # 살아 있는 프로세스인데 lsof가 답하지 않음
        self.assertEqual(self.rows()[("-w-app", A)]["why"], "확인 실패")

    def test_process_that_already_exited_does_not_block(self):
        p = subprocess.Popen(["true"])
        p.wait()
        self.session("-w-app", A)
        self.stub("ps", f"  {p.pid} claude\n")
        self.assertEqual(self.verdicts(), {A: "ASK"})

    # herdr (선택)
    def test_without_herdr_it_still_runs(self):
        self.session("-w-app", A)
        self.assertIn("herdr 없음", self.run_it())
        self.assertEqual(self.verdicts(), {A: "ASK"})

    def test_herdr_pane_keeps_its_folder(self):
        self.session("-w-app", A)
        self.session("-w-sub", B)
        self.session("-w-other", C)
        self.stub("herdr", '{"result":{"agents":[{"cwd":"/w/app","foreground_cwd":"/w/sub"}]}}')
        self.assertEqual(self.verdicts(), {A: "KEEP", B: "KEEP", C: "ASK"})
        self.assertEqual(self.verdicts("--no-herdr"), {A: "ASK", B: "ASK", C: "ASK"})

    def test_broken_herdr_keeps_everything(self):
        self.session("-w-app", A)
        for out in ("", "not json", '{"result":{}}', '{"result":{"agents":[{"title":"x"}]}}'):
            with self.subTest(out):
                self.stub("herdr", out, code=1)
                self.assertEqual(self.verdicts(), {A: "KEEP"})

    # 이름 중복
    def test_same_title_is_judged_per_session(self):
        self.session("-w-app", A, name="같은 제목", log_days=1)
        self.session("-w-app", B, name="같은 제목", log_days=30)
        rows = self.rows()
        self.assertEqual([rows[("-w-app", s)]["verdict"] for s in (A, B)], ["KEEP", "ASK"])
        self.assertEqual([rows[("-w-app", s)]["title"] for s in (A, B)], ["같은 제목"] * 2)

    def test_two_folders_with_the_same_project_name_are_both_kept(self):
        self.session("-w-my-app", A)     # /w/my-app 과 /w/my/app 은 같은 이름이 된다
        self.stub("ps", "  501 claude\n")
        self.stub("lsof", "p501\nfcwd\nn/w/my/app\n")
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    def test_same_id_in_two_projects_uses_newest_transcript(self):
        self.session("-w-app", A)
        self.write(f"projects/-w-copy/{A}.jsonl", "{}", 1)
        self.assertEqual(self.verdicts(), {A: "KEEP"})

    # 경로와 출력
    def test_space_quote_and_pipe_in_names(self):
        self.session("-w-app", A, [("my file's a|b.md", "x")], name="제목 | 막대")
        r = self.rows()[("-w-app", A)]
        self.assertEqual(r["verdict"], "REVIEW")
        self.assertIn("my file's a\\|b.md", r["files"])
        self.assertEqual(r["title"], "제목 \\| 막대")

    def test_transcript_body_is_not_printed(self):
        self.session("-w-app", A, name="제목")
        self.assertNotIn("숨길 내용", self.run_it())

    def test_small_keep_is_collapsed_only_without_all(self):
        self.session("-w-app", A, log_days=1)
        r = subprocess.run([sys.executable, "-I", SESSIONS, "--root", os.path.join(self.tmp, "root"),
                            "--projects", os.path.join(self.tmp, "projects"), "--no-herdr"],
                           capture_output=True, text=True, encoding="utf-8",
                           env={"PATH": self.bin.name + ":/usr/bin:/bin", "PYTHONUTF8": "1"})
        self.assertIn("KEEP 1개는 줄였다", r.stdout)

    def test_days_below_seven_is_refused(self):
        for bad in ("0", "-3", "nan", "1", "6", "6.9"):
            self.run_it("--days", bad, code=2)
        self.run_it("--days", "7")

    def test_nothing_changes_on_disk(self):
        self.session("-w-app", A, [("a.md", "x")])
        self.session("-w-app", B)
        before = self.tree()
        self.run_it()
        self.assertEqual(self.tree(), before)


class ScanTest(Temp):
    prefix = "dca it's 한글 "

    def run_it(self, *args, code=0):
        r = subprocess.run([sys.executable, "-I", SCAN, *args], capture_output=True, text=True, encoding="utf-8",
                           env={"PATH": "/usr/bin:/bin", "HOME": self.tmp, "PYTHONUTF8": "1"})
        self.assertEqual(r.returncode, code, r.stderr)
        return r.stdout

    def small(self, *args):
        return self.run_it(*args, self.tmp, "--min-dir-mb", "0.05", "--min-file-mb", "0.05")

    def paths(self, out, section):
        part = out.split(f"## {section}")[1].split("\n## ")[0]
        return [shlex.split(row.split(" | ")[2][:-2])[0] for row in part.splitlines()[3:] if row.startswith("| ")]

    def test_space_and_single_quote_paths_round_trip(self):
        f = self.write("it's a dir/big file's.bin", "x" * 200_000)
        out = self.small()
        self.assertEqual(self.paths(out, "큰 파일"), [f])
        self.assertEqual(set(self.paths(out, "큰 폴더")), {self.tmp, os.path.dirname(f)})

    def test_hidden_folders_are_counted(self):
        self.write(".cache/tool/blob", "x" * 200_000)
        self.assertIn(os.path.join(self.tmp, ".cache"), self.paths(self.small(), "큰 폴더"))

    def test_symlinks_are_not_followed_and_hard_links_count_once(self):
        f = self.write("a/blob", "x" * 200_000)
        os.makedirs(os.path.join(self.tmp, "b"))
        os.link(f, os.path.join(self.tmp, "b", "blob"))
        os.symlink(os.path.join(self.tmp, "a"), os.path.join(self.tmp, "c"))
        os.symlink(self.write("d.bin", "x" * 200_000), os.path.join(self.tmp, "e.bin"))
        out = self.small()
        self.assertEqual(len(self.paths(out, "큰 파일")), 2)   # 하드 링크 하나와 d.bin
        self.assertEqual(len(self.paths(out, "큰 폴더")), 2)   # 뿌리와 하드 링크 중 먼저 본 쪽

    def test_newest_date_of_a_folder(self):
        self.write("a/old", "x" * 200_000, 100)
        self.write("a/new", "x", 3)
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
        self.assertIn(day, self.small().split("## 큰 폴더")[1].split("## 큰 파일")[0])

    def test_small_target_is_still_shown(self):
        f = self.write("x.txt", "x")
        self.assertEqual(self.paths(self.run_it(f), "큰 폴더"), [f])
        self.assertEqual(self.paths(self.run_it(self.tmp), "큰 폴더"), [self.tmp])

    def test_unreadable_folder_is_reported(self):
        self.write("locked/a", "x")
        locked = os.path.join(self.tmp, "locked")
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o700)
        if os.access(locked, os.R_OK):
            self.skipTest("root로 실행 중")
        self.assertIn("읽지 못한 곳 1개", self.small())

    def test_root_system_and_volumes_are_refused(self):
        link = os.path.join(self.tmp, "link")
        os.symlink("/", link)
        for p in ("/", "/System", "/Volumes/Backup", "/volumes", link):
            self.run_it(p, code=2)

    def test_missing_path_is_refused(self):
        self.run_it(os.path.join(self.tmp, "없음"), code=2)

    def test_free_only(self):
        out = self.run_it("--free")
        self.assertIn("여유", out)
        self.assertNotIn("##", out)

    def test_free_works_without_library_folder(self):
        # 리눅스에는 /Library가 없다
        code = ("import os, runpy, sys\nreal = os.path.lexists\n"
                "os.path.lexists = lambda p: p != '/Library' and real(p)\n"
                f"sys.argv = ['scan.py', '--free']\nrunpy.run_path({SCAN!r}, run_name='__main__')")
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, encoding="utf-8",
                           env={"PATH": "/usr/bin:/bin", "HOME": self.tmp, "PYTHONUTF8": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("여유", r.stdout)

    # 승인 기록과 실행 직전 대조
    def record(self, *paths):
        rec = os.path.join(self.tmp, "record.json")
        with open(rec, "w", encoding="utf-8") as f:
            f.write(self.run_it("--record", *paths))
        return rec

    def test_record_has_raw_path_bytes_and_mtime_ns(self):
        f = self.write("it's\na|b/blob", "x" * 5000, 3)
        st = os.lstat(f)
        with open(self.record(f, os.path.dirname(f)), encoding="utf-8") as r:
            got = json.load(r)
        self.assertEqual([x["path"] for x in got], [f, os.path.dirname(f)])
        for x in got:
            self.assertEqual((x["bytes"], x["mtime_ns"]), (st.st_blocks * 512, st.st_mtime_ns))
            self.assertIn(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), x["shown"])

    def test_check_passes_when_nothing_changed(self):
        f = self.write("d/blob", "x" * 5000, 3)
        self.assertIn("같음: ", self.run_it("--check", self.record(os.path.dirname(f), f)))

    def test_check_stops_on_one_hour_difference(self):
        # 표에서는 날짜도 크기도 같아 보인다
        f = self.write("d/blob", "x" * 5000)
        noon = time.mktime((2025, 10, 1, 12, 0, 0, 0, 0, -1))
        os.utime(f, (noon, noon))
        rec, before = self.record(os.path.dirname(f)), self.run_it(os.path.dirname(f)).split("## 큰 폴더")[1]
        os.utime(f, (noon + 3600, noon + 3600))
        self.assertEqual(self.run_it(os.path.dirname(f)).split("## 큰 폴더")[1], before)
        self.assertIn("달라짐: ", self.run_it("--check", rec, code=1))

    def test_check_stops_on_size_link_or_unreadable(self):
        f = self.write("d/blob", "x" * 5000, 3)
        d, rec = os.path.dirname(f), self.record(os.path.dirname(f))
        self.write("d/more", "x" * 5000, 5)
        self.run_it("--check", rec, code=1)
        self.write("e/blob", "x" * 5000, 3)
        link = os.path.join(self.tmp, "link")
        os.symlink(d, link)
        rec = self.record(os.path.join(self.tmp, "e"))
        os.rename(os.path.join(self.tmp, "e"), os.path.join(self.tmp, "e2"))
        os.rename(link, os.path.join(self.tmp, "e"))
        self.run_it("--check", rec, code=1)
        os.makedirs(os.path.join(self.tmp, "e2", "locked"))
        rec, locked = self.record(os.path.join(self.tmp, "e2")), os.path.join(self.tmp, "e2", "locked")
        self.run_it("--check", rec)
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o700)
        if not os.access(locked, os.R_OK):
            self.run_it("--check", rec, code=1)

    def test_check_refuses_missing_path_and_broken_record(self):
        f = self.write("gone/blob", "x")
        rec = self.record(f)
        os.unlink(f)
        self.run_it("--check", rec, code=2)
        for text in ("", "[]", "{}", "[1]", '[{"path":"/x"}]', '[{"path":"/","bytes":0,"mtime_ns":0}]'):
            self.run_it("--check", self.write("bad.json", text), code=2)
        self.run_it("--check", os.path.join(self.tmp, "없음.json"), code=2)
        self.run_it("--record", code=2)
        self.run_it("--check", "", code=2)               # 빈 변수가 들어와도 0으로 끝나지 않는다
        self.run_it("--check", rec, "--free", code=2)

    def test_printed_paths_give_the_real_path_back_in_a_shell(self):
        # 예전에는 표의 개행과 막대가 다른 글자로 바뀌어 그대로 쓰면 다른 경로가 됐다
        f = self.write("it's\na|b\\c\td/blob 파일", "x" * 200_000)
        table = next(row for row in self.small().split("## 큰 파일")[1].splitlines() if "blob" in row)
        line = next(x for x in self.run_it("--check", self.record(f)).splitlines() if x.startswith("같음: "))
        for text in (table.split(" | ")[2][:-2], line[len("같음: "):]):
            r = subprocess.run(["bash", "-c", "printf %s " + text], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.stdout, f)

    def test_nothing_changes_on_disk(self):
        self.write("a/b", "x")
        before = self.tree()
        self.small()
        self.assertEqual(self.tree(), before)


class Documents(Temp):
    prefix = "dca it's home "

    def test_scripts_have_no_delete_or_write_code(self):
        for name in os.listdir(os.path.join(SKILL, "scripts")):
            if name.endswith(".py"):
                found = re.findall(r"os\.(?:remove|unlink|rmdir|rename|replace|chmod|truncate)|rmtree|shutil\.move|"
                                   r"\.unlink\(|\brm\b|open\([^)]*[\"'][wax]b?[\"']", read("scripts", name))
                self.assertEqual(found, [], name)

    def test_documents_avoid_known_traps(self):
        text = read("SKILL.md") + read("references", "classify.md") + read("README.md")
        self.assertNotIn("xargs -I", text)
        self.assertNotRegex(text, r"find / ")
        self.assertNotIn("CANDIDATE", text)

    def test_homebrew_command_asks_for_what_is_outside_the_cache(self):
        # brew cleanup은 승인받은 캐시 경로 밖의 옛 설치 버전도 지운다
        row = next(x for x in read("references", "classify.md").splitlines() if "brew cleanup -n" in x)
        self.assertIn("캐시 밖", row)
        self.assertIn("따로 승인", row)
        self.assertIn("캐시 밖", read("SKILL.md"))

    def test_skill_uses_the_record_not_the_table(self):
        for text in ("scan.py --record", "scan.py --check"):
            self.assertIn(text, read("SKILL.md"))

    def test_node_modules_command_handles_spaces_and_quotes(self):
        cmd = next(line for line in read("references", "classify.md").splitlines() if line.startswith("find ~/"))
        for d in ("it's app", "plain"):
            self.write(f"Projects/{d}/node_modules/x/index.js", "x" * 50_000)
        r = subprocess.run(["/bin/sh", "-c", cmd], capture_output=True, text=True,
                           env={"PATH": "/usr/bin:/bin", "HOME": self.tmp})
        self.assertEqual(r.stderr, "")
        for d in ("it's app", "plain"):
            self.assertIn(f"Projects/{d}/node_modules", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
