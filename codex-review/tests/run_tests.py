#!/usr/bin/env python3
"""codex_review.py 테스트. 진짜 codex 대신 가짜 실행 파일을 쓴다(네트워크·유료 호출 없음).

사용: python3 -I tests/run_tests.py
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "codex_review.py")

FAKE = f'''#!{sys.executable}
import json, os, subprocess, sys, time
args = sys.argv[1:]
stdin = sys.stdin.read()
json.dump(dict(args=args, stdin=stdin), open(os.environ["FAKE_REC"], "w"))
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "sleep":
    time.sleep(30)
if mode == "child":   # 래퍼가 본체를 하위 프로세스로 띄우는 설치본 흉내
    subprocess.Popen(["/bin/sh", "-c", "sleep 4; echo alive > " + os.environ["FAKE_MARK"]]).wait()
if mode != "empty":
    reply = "ok\\n" if "Reply with exactly: ok" in stdin else "## findings\\n- none\\n"
    if mode == "badping":
        reply = "cannot help\\n"
    open(args[args.index("-o") + 1], "w").write(reply)
print("codex log line")
sys.exit(3 if mode == "fail" else 0)
'''


class CodexReviewTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="codex-review-test-")
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.fake = self.path("codex")
        self.write("codex", FAKE)
        os.chmod(self.fake, 0o755)
        self.work = self.path("work")
        os.makedirs(self.work)
        self.prompt = self.write("r1.md", "이 폴더를 리뷰해 줘.")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("CODEX_REVIEW_")}
        self.env.update(CODEX_BIN=self.fake, FAKE_REC=self.path("rec.json"), FAKE_MARK=self.path("mark"),
                        HOME=self.path("home"), TMPDIR=self.root)

    def path(self, *names):
        return os.path.join(self.root, *names)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def call(self, *args, mode="ok", **env):
        r = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, cwd=self.work,
                           env=dict(self.env, FAKE_MODE=mode, **env))
        lines = r.stdout.strip().splitlines()
        return r.returncode, json.loads(lines[-1]) if lines else {}, r.stderr

    def review(self, *args, **kw):
        return self.call("--prompt", self.prompt, "--cd", self.work, *args, **kw)

    def fake_call(self):
        with open(self.path("rec.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def called(self):
        return os.path.exists(self.path("rec.json"))

    # 호출 모양
    def test_default_shape(self):
        code, res, _ = self.review()
        a = self.fake_call()["args"]
        self.assertEqual((code, res["exit"], res["out"]), (0, 0, self.path("r1.out.md")))
        self.assertEqual(a[:2], ["exec", "--skip-git-repo-check"])
        self.assertEqual((a[a.index("-s") + 1], a[a.index("-C") + 1], a[a.index("-o") + 1]),
                         ("read-only", self.work, self.path("r1.out.md")))
        with open(res["log"], encoding="utf-8") as fh:
            self.assertIn("codex log line", fh.read())

    def test_no_model_or_effort_unless_given(self):
        self.review()
        a = self.fake_call()["args"]
        self.assertNotIn("-m", a)
        self.assertFalse([x for x in a if "reasoning" in x])

    def test_model_from_env_and_flag(self):
        self.review(CODEX_REVIEW_MODEL="model-a")
        a = self.fake_call()["args"]
        self.assertEqual(a[a.index("-m") + 1], "model-a")
        self.review("--model", "model-b", CODEX_REVIEW_MODEL="model-a")
        a = self.fake_call()["args"]
        self.assertEqual(a[a.index("-m") + 1], "model-b")

    def test_prompt_goes_through_stdin(self):
        self.review()
        rec = self.fake_call()
        self.assertEqual(rec["stdin"], "이 폴더를 리뷰해 줘.")
        self.assertEqual(rec["args"][-1], "-")
        self.assertFalse([x for x in rec["args"] if "리뷰해" in x])

    def test_long_prompt_beyond_argument_limit(self):
        self.write("r1.md", "x" * 3_000_000)
        code, _, _ = self.review()
        self.assertEqual((code, len(self.fake_call()["stdin"])), (0, 3_000_000))

    def test_optional_flags(self):
        self.review("--web", "--add-dir", self.path("home"), "--sandbox", "workspace-write", "--effort", "high")
        a = self.fake_call()["args"]
        self.assertIn('web_search="live"', a)
        self.assertIn('model_reasoning_effort="high"', a)
        self.assertEqual((a[a.index("--add-dir") + 1], a[a.index("-s") + 1]), (self.path("home"), "workspace-write"))

    def test_web_is_not_passed_by_default(self):
        self.review()
        self.assertFalse([x for x in self.fake_call()["args"] if "web_search" in x])

    def test_effort_rejects_config_injection(self):
        code, _, err = self.review("--effort", 'low" , x="1')
        self.assertEqual((code, self.called()), (2, False))
        self.assertIn("--effort", err)

    def test_relative_paths_become_absolute(self):
        self.call("--prompt", "../r1.md", "--cd", ".")
        a = self.fake_call()["args"]
        self.assertEqual((a[a.index("-C") + 1], a[a.index("-o") + 1]), (self.work, self.path("r1.out.md")))

    def test_dry_run_does_not_call(self):
        code, res, _ = self.review("--dry-run")
        self.assertEqual((code, res["dry_run"], self.called()), (0, True, False))
        self.assertIn(self.work, res["cmd"])
        self.assertFalse(os.path.exists(self.path("r1.out.md.log")))

    # 막는 폴더
    def test_block_list_is_empty_by_default(self):
        self.assertEqual(self.review("--add-dir", "~/anything")[0], 0)

    def test_block_list_checks_cd_and_add_dir(self):
        os.makedirs(self.path("home", "secret", "sub"))
        os.symlink(self.path("home", "secret"), self.path("link"))
        block = "~/secret" + os.pathsep + self.path("other")
        for bad in ("~/secret", "~/secret/sub", self.path("link"), self.path("other", "x")):
            code, res, _ = self.review("--add-dir", bad, CODEX_REVIEW_BLOCK=block)
            self.assertEqual(code, 2, bad)
            self.assertIn("막힘", res["error"])
        code, _, _ = self.call("--prompt", self.prompt, "--cd", "~/secret/sub", CODEX_REVIEW_BLOCK=block)
        self.assertEqual((code, self.called()), (2, False))
        self.assertEqual(self.review(CODEX_REVIEW_BLOCK=block)[0], 0)

    def test_block_list_catches_parent_folder(self):
        os.makedirs(self.path("home", "secret"))
        code, _, _ = self.call("--prompt", self.prompt, "--cd", "~", CODEX_REVIEW_BLOCK="~/secret")
        self.assertEqual((code, self.called()), (2, False))

    def test_block_list_does_not_match_sibling_prefix(self):
        os.makedirs(self.path("home", "secret-not"))
        self.assertEqual(self.review("--add-dir", "~/secret-not", CODEX_REVIEW_BLOCK="~/secret")[0], 0)

    # 실행 기록
    def test_run_log_is_off_by_default(self):
        self.review()
        self.assertFalse(os.path.exists(self.path("home")))

    def test_run_log_keeps_metadata_only(self):
        log = self.path("logs", "runs.jsonl")
        self.review(CODEX_REVIEW_LOG=log)
        with open(log, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {"ts", "cwd", "ping", "exit", "seconds", "out_bytes", "model", "effort", "sandbox"})

    # 실패를 성공으로 읽지 않기
    def test_codex_failure_code_is_returned(self):
        code, res, _ = self.review(mode="fail")
        self.assertEqual((code, res["exit"]), (3, 3))

    def test_empty_result_is_failure_and_old_result_is_moved(self):
        self.review()
        code, res, _ = self.review(mode="empty")
        self.assertEqual(code, 1)
        self.assertIn("비어", res["error"])
        self.assertTrue(os.path.exists(self.path("r1.out.md.prev")))
        self.assertFalse(os.path.exists(self.path("r1.out.md")))

    def test_timeout_returns_124(self):
        code, res, _ = self.review("--timeout-min", "0.02", mode="sleep")
        self.assertEqual(code, 124)
        self.assertIn("멈췄", res["error"])

    def test_timeout_stops_child_processes(self):
        self.assertEqual(self.review("--timeout-min", "0.02", mode="child")[0], 124)
        time.sleep(4.5)
        self.assertFalse(os.path.exists(self.path("mark")), "하위 프로세스가 살아남음")

    def test_sigterm_stops_child_processes(self):
        p = subprocess.Popen([sys.executable, "-I", SCRIPT, "--prompt", self.prompt, "--cd", self.work],
                             env=dict(self.env, FAKE_MODE="child"), stdout=subprocess.DEVNULL)
        for _ in range(100):
            if self.called():
                break
            time.sleep(0.05)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=15), 143)
        time.sleep(4.5)
        self.assertFalse(os.path.exists(self.path("mark")), "하위 프로세스가 살아남음")

    def test_bad_input_is_rejected_before_calling(self):
        self.write("empty.md", "  \n")
        self.assertIn("비어", self.call("--prompt", self.path("empty.md"))[2])
        self.assertEqual(self.call()[0], 2)
        self.assertEqual(self.call("--prompt", self.path("none.md"))[0], 2)
        self.assertEqual(self.call("--prompt", self.prompt, "--cd", self.path("none"))[0], 2)
        self.assertEqual(self.review("--out", self.path("none", "o.md"))[0], 2)
        self.assertEqual(self.review("--out", self.prompt)[0], 2)
        self.assertFalse(self.called())

    # 경로 충돌: 파일을 열기 전에 거절하고 아무것도 바꾸지 않는다
    def refused(self, *args, keep=None, **env):
        code, res, _ = self.call("--cd", self.work, *args, **env)
        self.assertEqual((code, self.called()), (2, False), args)
        self.assertIn("같은 파일", res["error"])
        if keep:
            with open(keep, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "원본")

    def test_prompt_must_not_be_the_log_or_prev_of_the_result(self):
        for name in ("review.log", "review.prev"):
            prompt = self.write(name, "원본")
            self.refused("--prompt", prompt, "--out", self.path("review"), keep=prompt)

    def test_collision_is_found_through_links(self):
        prompt = self.write("p.md", "원본")
        os.symlink(prompt, self.path("a.log"))
        os.link(prompt, self.path("b.log"))
        for out in ("a", "b"):
            self.refused("--prompt", prompt, "--out", self.path(out), keep=prompt)
        os.symlink(self.path("c"), self.path("c.log"))   # 로그가 결과를 덮는다
        self.refused("--prompt", prompt, "--out", self.path("c"), keep=prompt)

    def test_collision_is_found_in_dry_run_and_run_log(self):
        prompt = self.write("review.log", "원본")
        self.refused("--prompt", prompt, "--out", self.path("review"), "--dry-run", keep=prompt)
        self.refused("--prompt", prompt, CODEX_REVIEW_LOG=prompt, keep=prompt)

    def test_result_path_must_not_be_a_folder(self):
        for out in (self.work, self.path("x")):
            os.makedirs(self.path("x.log"), exist_ok=True)
            code, res, _ = self.review("--out", out)
            self.assertEqual((code, self.called()), (2, False), out)
            self.assertIn("폴더", res["error"])
        self.assertTrue(os.path.isdir(self.work))

    def test_missing_codex(self):
        code, res, _ = self.review(CODEX_BIN=self.path("no-codex"))
        self.assertEqual(code, 127)
        self.assertIn("찾지 못했어요", res["error"])

    # ping
    def test_ping(self):
        code, res, _ = self.call("--ping")
        self.assertEqual((code, res["ping_ok"]), (0, True))
        self.assertIn('model_reasoning_effort="low"', self.fake_call()["args"])

    def test_ping_unexpected_reply(self):
        code, res, _ = self.call("--ping", mode="badping")
        self.assertEqual((code, res["ping_ok"]), (1, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
