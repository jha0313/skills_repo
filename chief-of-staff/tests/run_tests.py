#!/usr/bin/env python3
"""inbox.py와 틀 검사. 표준 라이브러리, 임시 폴더만 쓴다. 네트워크·유료 호출 없음."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
INBOX = SKILL / "scripts" / "inbox.py"
TODAY = "2026-01-18"
DONE = "RESULT: done\nSUMMARY: 끝냈다\nEVIDENCE: make test → 12 passed\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="chief-test-"))
        self.addCleanup(shutil.rmtree, self.home)

    def task(self, tid, result=None, project="acme-web", kind="run", **head):
        folder = self.home / "tasks" / tid
        folder.mkdir(parents=True)
        head = {"project": project, "kind": kind, "started": "2026-01-15 09:00", **head}
        lines = [f"{k}: {v}" for k, v in head.items()]
        (folder / "brief.md").write_text("# " + tid + "\n\n" + "\n".join(lines) + "\n\n## 사용자 의도\n", "utf-8")
        if isinstance(result, bytes):
            (folder / "result.md").write_bytes(result)
        elif result is not None:
            (folder / "result.md").write_text(result, "utf-8")
        return folder

    def focus(self, text):
        (self.home / "focus.md").write_text(text, "utf-8")

    def run_raw(self, home=None, *args):
        env = {**os.environ, "CHIEF_OF_STAFF_HOME": str(home or self.home)}
        return subprocess.run([sys.executable, "-I", str(INBOX), "--today", TODAY, *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=30)

    def board(self):
        proc = self.run_raw()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return proc.stdout

    def section(self, title, out=None):
        out = out or self.board()
        m = re.search(rf"^== {re.escape(title)} \(\d+\)\n((?:  .*\n?)*)", out, re.M)
        return m[1] if m else ""

    def order(self, title="지금 볼 것"):
        return re.findall(r"^  (?:\d+\.|-) (\S+) ·", self.section(title), re.M)


class Scenario(Base):
    """가짜 프로젝트 2개, 작업 5개: 끝남, 결정 필요, 사람 필요, 막힘, 진행 중."""

    def setUp(self):
        super().setUp()
        self.focus('# 우선순위\n- acme-web: "결제가 먼저" (2026-01-05)\n- demo-api: "그다음" (2026-01-05)\n')
        self.task("pay-fix", DONE, kind="ship", closed="2026-01-16 머지됨")
        self.task("api-plan", "RESULT: needs-decision\nSUMMARY: 두 안\nDECISION: 캐시를 넣을까? 추천은 넣기\n",
                  project="demo-api", kind="scout")
        self.task("api-login", "RESULT: needs-human\nHUMAN: 인증 · 터미널에서 gh auth login\n", project="demo-api")
        self.task("web-build", "RESULT: blocked\nSUMMARY: 패키지 서버가 503\nEVIDENCE: npm ci 로그\n")
        self.task("web-copy", None, kind="ship")

    def test_groups(self):
        self.assertEqual(self.order("내 차례"), ["api-login", "api-plan", "web-build"])
        self.assertEqual(self.order("작업 중"), ["web-copy"])
        self.assertEqual(self.order("끝남"), ["pay-fix"])

    def test_people_before_blocked_even_with_lower_priority(self):
        self.assertEqual(self.order(), ["api-login", "api-plan", "web-build"])
        self.assertIn("나머지: 내 차례 0 · 읽을 것 0 · 작업 중 1 · 끝남 1", self.board())

    def test_reason_is_shown(self):
        out = self.board()
        self.assertIn("needs-human: 인증 · 터미널에서 gh auth login", out)
        self.assertIn("needs-decision: 캐시를 넣을까?", out)

    def test_deadline_sits_between_people_and_blocked(self):
        (self.home / "tasks/web-copy/brief.md").write_text(
            "project: acme-web\nkind: ship\nstarted: 2026-01-15\ndue: 2026-01-20\n", "utf-8")
        self.assertEqual(self.order(), ["api-login", "api-plan", "web-copy"])
        self.assertIn("나머지: 내 차례 1", self.board())

    def test_reads_only(self):
        def snapshot():
            return {p: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else b"") for p in self.home.rglob("*")}
        before = snapshot()
        self.board()
        self.assertEqual(before, snapshot())


class Sorting(Base):
    def test_overdue_first_among_non_people(self):
        self.task("late", DONE, due="2026-01-15")
        self.task("soon", DONE, due="2026-01-19")
        self.task("stuck", "RESULT: failed\nSUMMARY: 테스트 3개 실패\n")
        self.assertEqual(self.order(), ["late", "soon", "stuck"])
        out = self.board()
        self.assertIn("지남 3일", out)
        self.assertIn("D-1", out)

    def test_people_before_overdue(self):
        self.task("late", DONE, due="2026-01-01")
        self.task("ask", "RESULT: needs-decision\nDECISION: 어느 쪽?\n")
        self.assertEqual(self.order(), ["ask", "late"])

    def test_deadline_orders_people_items(self):
        self.task("a-person", "RESULT: needs-human\nHUMAN: 허용\n")
        self.task("z-person", "RESULT: needs-human\nHUMAN: 허용\n", due="2026-01-18")
        self.assertEqual(self.order(), ["z-person", "a-person"])
        self.assertIn("오늘", self.board())

    def test_far_deadline_does_not_jump_the_queue(self):
        self.task("far", DONE, due="2026-03-01")
        self.task("stuck", "RESULT: blocked\nSUMMARY: 막힘\n")
        self.assertEqual(self.order(), ["stuck", "far"])

    def test_focus_order_breaks_ties(self):
        self.focus("1. demo-api: 먼저\n2. acme-web: 다음\n")
        self.task("a-web", DONE)
        self.task("b-api", DONE, project="demo-api")
        self.task("c-none", DONE, project="other")
        self.assertEqual(self.order(), ["b-api", "a-web", "c-none"])

    def test_three_and_the_rest(self):
        for n in range(5):
            self.task(f"t{n}", DONE)
        self.assertEqual(len(self.order()), 3)
        self.assertIn("나머지: 내 차례 0 · 읽을 것 2 · 작업 중 0 · 끝남 0", self.board())

    def test_closed_task_with_past_due_is_not_urgent(self):
        self.task("old", DONE, due="2026-01-01", closed="2026-01-02 받아들임")
        self.assertEqual(self.order(), [])

    def test_quiet_working_task_is_not_in_top(self):
        self.task("working")
        self.assertEqual(self.section("지금 볼 것"), "  없음\n")
        self.assertEqual(self.order("작업 중"), ["working"])


class BrokenResults(Base):
    def assert_broken(self, result):
        self.task("bad", result)
        line = self.section("내 차례")
        self.assertIn("RESULT를 읽지 못함", line)
        self.assertNotIn("bad", self.section("읽을 것"))

    def test_empty(self):
        self.assert_broken("")

    def test_no_result_line(self):
        self.assert_broken("다 끝났습니다!\n")

    def test_unknown_value(self):
        self.assert_broken("RESULT: 완료\nEVIDENCE: 봄\n")

    def test_unfilled_template_is_not_done(self):
        worker = (SKILL / "references/worker.md").read_text("utf-8")
        block = re.search(r"```\n(RESULT:.*?)```", worker, re.S)[1]
        self.assert_broken(block)

    def test_two_different_results(self):
        self.assert_broken("RESULT: failed\nSUMMARY: x\n\nRESULT: done\nEVIDENCE: y\n")

    def test_binary(self):
        self.assert_broken(b"\xff\xfe\x00\x01RESULT\x00")

    def test_result_is_a_folder(self):
        folder = self.task("bad")
        (folder / "result.md").mkdir()
        self.assertIn("RESULT를 읽지 못함", self.section("내 차례"))

    def test_commented_result_is_ignored(self):
        self.assert_broken("<!-- RESULT: done -->\nSUMMARY: 아직\n")

    def test_done_without_evidence_is_not_done(self):
        self.task("bad", "RESULT: done\nSUMMARY: 다 됐다\nEVIDENCE:\nFILES: a.py\n")
        self.assertIn("EVIDENCE가 비어 있음", self.section("내 차례"))

    def test_crlf_bom_fence_and_multiline_evidence_are_fine(self):
        self.task("ok", "\ufeffRESULT: Done\r\nSUMMARY: 됨\r\nEVIDENCE:\r\n```\r\n- make test\r\n```\r\n".encode())
        self.assertEqual(self.order("읽을 것"), ["ok"])


class Verification(Base):
    def test_unchecked_done_is_labelled_as_claim(self):
        self.task("t", DONE)
        mark = hashlib.sha256(DONE.encode()).hexdigest()[:8]
        self.assertIn(f"확인 전(작업자의 말), 지문 {mark}", self.section("읽을 것"))

    def test_checked(self):
        mark = hashlib.sha256(DONE.encode()).hexdigest()[:8]
        self.task("t", DONE, checked=f"{mark} 로그 확인")
        self.assertIn("확인됨: 끝냈다", self.section("읽을 것"))

    def test_result_changed_after_check(self):
        self.task("t", DONE, checked="00000000 로그 확인")
        self.assertIn("확인 뒤 결과가 바뀜", self.section("읽을 것"))

    def test_closed_without_check_is_flagged(self):
        self.task("t", DONE, closed="2026-01-17 받아들임")
        self.assertIn("확인 기록 없음", self.section("끝남"))

    def test_cancelled_needs_no_check(self):
        self.task("t", None, closed="2026-01-17 취소")
        self.assertNotIn("확인 기록 없음", self.section("끝남"))

    def test_ask_is_the_persons_turn(self):
        self.task("t", DONE, kind="ship", ask="머지할까? https://github.com/example/acme-web/pull/12")
        self.assertIn("답을 기다림: 머지할까? https://github.com/example/acme-web/pull/12", self.section("내 차례"))
        self.assertEqual(self.order("읽을 것"), [])

    def test_previous_round_result_is_ignored(self):
        folder = self.task("t")
        (folder / "result-1.md").write_text("RESULT: needs-decision\nDECISION: 옛 질문\n", "utf-8")
        self.assertEqual(self.order("작업 중"), ["t"])
        self.assertNotIn("옛 질문", self.board())


class Folders(Base):
    def test_empty_home(self):
        out = self.board()
        self.assertIn("== 지금 볼 것 (0)\n  없음", out)
        self.assertIn("나머지: 내 차례 0 · 읽을 것 0 · 작업 중 0 · 끝남 0", out)
        self.assertNotIn("경고", out)

    def test_missing_home_is_an_error_not_an_empty_board(self):
        proc = self.run_raw(self.home / "nope")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("상태 폴더가 없음", proc.stderr)

    def test_home_option_wins(self):
        self.task("t", DONE)
        proc = self.run_raw(self.home / "nope", "--home", str(self.home))
        self.assertIn("t · acme-web/run", proc.stdout)

    def test_stray_files_are_skipped(self):
        self.task("t", DONE)
        (self.home / "tasks/.DS_Store").write_bytes(b"\0")
        (self.home / "tasks/note.md").write_text("RESULT: failed", "utf-8")
        (self.home / "tasks/.trash").mkdir()
        self.assertEqual(self.order(), ["t"])

    def test_task_without_brief(self):
        (self.home / "tasks/orphan").mkdir(parents=True)
        self.assertIn("brief.md가 없음", self.section("내 차례"))

    def test_unknown_kind_and_bad_due_warn(self):
        self.task("t", DONE, kind="deploy", due="2026-13-40")
        warn = self.section("경고")
        self.assertIn("kind가 ship·run·scout가 아님", warn)
        self.assertIn("due를 읽지 못함", warn)

    def test_fields_after_first_heading_are_not_state(self):
        folder = self.task("t")
        brief = folder / "brief.md"
        brief.write_text(brief.read_text("utf-8") + "closed: 2026-01-01 본문 예시\nask: 예시\n", "utf-8")
        self.assertEqual(self.order("작업 중"), ["t"])

    def test_control_characters_are_removed(self):
        self.task("t", "RESULT: failed\nSUMMARY: \x1b[31m빨강\x1b[0m\x07 끝\n")
        out = self.board()
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)

    def test_done_list_is_cut(self):
        for n in range(13):
            self.task(f"t{n:02}", None, closed="2026-01-10 끝")
        self.assertIn("외 3개", self.section("끝남"))


class Focus(Base):
    def test_project_deadline_without_task(self):
        self.focus("- 2026-01-20 acme-web: 결제 화면 공개\n- 2026-03-20 demo-api: 먼 일\n")
        self.assertIn("마감 · acme-web · D-2 · 결제 화면 공개 (맡긴 작업 없음)", self.section("지금 볼 것"))
        self.assertNotIn("먼 일", self.board())

    def test_project_deadline_merges_into_task_with_same_due(self):
        self.focus("- 2026-01-20 acme-web: 결제 화면 공개\n")
        self.task("pay", DONE, due="2026-01-20")
        self.assertEqual(self.order(), ["pay"])
        self.assertEqual(self.section("마감"), "")

    def test_overdue_project_deadline(self):
        self.focus("- 2026-01-10 acme-web: 공개\n")
        self.task("t", DONE)
        self.assertIn("지남 8일 · 공개 (열린 작업 1개)", self.section("지금 볼 것"))

    def test_identical_deadlines_are_counted_one_by_one(self):
        self.focus("- 2026-01-20 acme-web: 공개\n" * 4)
        self.assertIn("끝남 0", self.board())
        self.assertIn("마감 1", re.search(r"^나머지: .*$", self.board(), re.M)[0])

    def test_unreadable_lines_warn(self):
        self.focus("- 이번 주는 결제 먼저\n- 2026-99-01 acme-web: 날짜 오류\n- 2026-01-20\n")
        warn = self.section("경고")
        for number in (1, 2, 3):
            self.assertIn(f"focus.md {number}번째 줄", warn)

    def test_priority_line(self):
        self.focus('- acme-web: "먼저"\n- demo-api\n')
        self.assertIn("우선순위: acme-web > demo-api", self.board())


class Package(Base):
    def test_templates_are_inert(self):
        for name in ("focus.md", "decisions.md", "projects.md"):
            shutil.copy(SKILL / "assets" / name, self.home / name)
        out = self.board()
        self.assertNotIn("경고", out)
        self.assertNotIn("우선순위:", out)
        folder = self.home / "tasks/new"
        folder.mkdir(parents=True)
        shutil.copy(SKILL / "assets/brief.md", folder / "brief.md")
        self.assertIn("시작 전", self.section("작업 중"))

    def test_frontmatter_and_length(self):
        text = (SKILL / "SKILL.md").read_text("utf-8")
        self.assertLessEqual(len(text.splitlines()), 100)
        self.assertEqual(re.search(r"^name: (.+)$", text, re.M)[1], SKILL.name)
        desc = re.search(r"^description: >-\n((?:  .*\n)+)", text, re.M)[1]
        self.assertLessEqual(len(" ".join(desc.split())), 350)
        for field in re.findall(r"^([a-z-]+):", text.split("---")[1], re.M):
            self.assertIn(field, ("name", "description", "license", "compatibility", "metadata"))

    def test_trigger_needs_several_projects(self):
        desc = (SKILL / "SKILL.md").read_text("utf-8").split("---")[1]
        for single in ('"상태 어때?"', '"이거 맡아 줘"', '"이번 주는 이게 먼저야"'):
            self.assertNotIn(single, desc)
        self.assertIn("여러 프로젝트를 두고", desc)
        self.assertIn("쓰지 않는다", desc)

    def test_one_approval_has_one_executor(self):
        """비서실장만 승인을 실행한다. 작업자 쪽 문서가 다르게 말하면 같은 행동이 두 번 나간다."""
        skill = (SKILL / "SKILL.md").read_text("utf-8")
        worker = (SKILL / "references/worker.md").read_text("utf-8")
        projects = (SKILL / "assets/projects.md").read_text("utf-8")
        self.assertIn("비서실장만", skill)
        self.assertNotIn("그 행동 한 번만 한다", worker)
        self.assertNotIn("승인 없이 그 명령을", projects)
        for text in (worker, projects):
            self.assertIn("비서실장이 실행한다", text)

    def test_interrupted_approval_looks_outside_first(self):
        for doc in ("SKILL.md", "assets/decisions.md"):
            self.assertIn("실행 시작", (SKILL / doc).read_text("utf-8"), doc)
        self.assertIn("밖의 결과부터", (SKILL / "SKILL.md").read_text("utf-8"))

    def test_masking_wins_over_verbatim(self):
        """'원문 그대로'라고 적은 문서에는 가림 규칙이 함께 있다."""
        for doc in ("SKILL.md", "references/dispatch.md", "assets/brief.md", "assets/decisions.md"):
            self.assertIn("[가림]", (SKILL / doc).read_text("utf-8"), doc)

    def test_links_exist(self):
        for doc in [SKILL / "SKILL.md", *SKILL.glob("references/*.md")]:
            for link in re.findall(r"\]\(([^)#\s]+)", doc.read_text("utf-8")):
                if not link.startswith("http"):
                    self.assertTrue((doc.parent / link).exists(), f"{doc.name}: {link}")

    def test_no_personal_paths(self):
        for path in SKILL.rglob("*"):
            if path.suffix in (".md", ".py"):
                text = path.read_text("utf-8")
                self.assertIsNone(re.search(r"/(Users|home)/[a-z]|[\w.]+@[\w-]+\.\w+", text), path.name)

    def test_first_screen_says_rules_are_not_enforced(self):
        self.assertIn("기계 강제가 없다", "\n".join((SKILL / "SKILL.md").read_text("utf-8").splitlines()[:22]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
