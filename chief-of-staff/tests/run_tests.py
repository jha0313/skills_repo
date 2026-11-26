#!/usr/bin/env python3
"""inbox.py·route.py·usage.py와 틀 검사. 표준 라이브러리, 임시 폴더만 쓴다. 네트워크·유료 호출 없음."""
import datetime as dt
import hashlib
import json
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
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL / "scripts"))
import route  # noqa: E402
import usage  # noqa: E402
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

    def test_working_task_shows_where_the_worker_is(self):
        self.task("seen", worker="herdr pay_fix, wT:t2")
        self.task("unknown")
        out = self.section("작업 중")
        self.assertIn("seen · acme-web/run · 시작 2026-01-15 09:00, 결과 없음, 작업자 herdr pay_fix, wT:t2\n", out)
        self.assertIn("unknown · acme-web/run · 시작 2026-01-15 09:00, 결과 없음\n", out)

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


class UnmovedResult(Base):
    def test_result_left_in_the_out_folder_is_shown(self):
        """astra 리뷰: Codex 작업자의 결과를 옮기기 전에 세션이 끊기면 보고판이 '작업 중'으로만 보이던 일."""
        folder = self.task("cx-task", kind="scout")
        (folder / "out").mkdir()
        self.assertIn("cx-task", self.section("작업 중"))
        (folder / "out" / "result.md").write_text("RESULT: needs-decision\nDECISION: a 또는 b\n", "utf-8")
        out = self.board()
        self.assertIn("out/result.md가 있음", out)
        self.assertNotIn("cx-task", self.section("작업 중", out))
        (folder / "result.md").write_text("RESULT: needs-decision\nSUMMARY: s\nDECISION: a 또는 b\n", "utf-8")
        self.assertIn("needs-decision: a 또는 b", self.board())   # 옮긴 뒤에는 그 결과대로


class Focus(Base):
    def test_project_deadline_without_task(self):
        self.focus("- 2026-01-20 acme-web: 결제 화면 공개\n- 2026-03-20 demo-api: 먼 일\n")
        self.assertIn("마감 · acme-web · D-2 · 결제 화면 공개 (맡긴 작업 없음)", self.section("지금 볼 것"))
        self.assertNotIn("먼 일", self.board())

    def test_project_deadline_is_kept_next_to_task_with_same_due(self):
        """날짜만 같다고 작업이 그 마감을 맡은 것은 아니다. 마감 이름은 사라지지 않는다."""
        self.focus("- 2026-01-20 acme-web: 고객 검토\n- 2026-01-20 acme-web: 운영 전환\n")
        self.task("pay", DONE, due="2026-01-20")
        self.assertIn("pay", self.order())
        for name in ("고객 검토", "운영 전환"):
            self.assertIn(f"{name} (열린 작업 1개)", self.section("마감"))

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

    def test_trigger_has_manager_only_words(self):
        """'너는 관리만 해'와 워커 세션 요청에 켜지지 않던 일(2026-11-25)."""
        desc = (SKILL / "SKILL.md").read_text("utf-8").split("---")[1]
        for phrase in ('"너는 관리만 해"', '"워커 세션에서 해"', '"워커 세션 만들어서 맡겨"', '"비서실장"', '"chief of staff"'):
            self.assertIn(phrase, desc)

    def test_one_approval_has_one_executor(self):
        """작업자 한 명만 승인을 실행한다. 문서마다 다르게 말하면 같은 행동이 두 번 나가거나 아무도 하지 않는다."""
        step6 = (SKILL / "SKILL.md").read_text("utf-8").split("### 6.")[1].split("### 7.")[0]
        self.assertIn("**그 작업의 작업자 한 명만, 한 번만** 실행한다. 비서실장은 하지 않는다", step6)
        self.assertRegex(step6, "push와 PR.*작업자")
        for doc in ("SKILL.md", "references/worker.md", "references/dispatch.md", "assets/brief.md", "assets/projects.md"):
            self.assertIn("승인받은 행동", (SKILL / doc).read_text("utf-8"), doc)
        self.assertIn("실패했으면 이어 시키지 않고 다시 묻는다", (SKILL / "references/dispatch.md").read_text("utf-8"))

    def test_no_doc_says_the_chief_executes(self):
        for path in SKILL.rglob("*.md"):
            text = path.read_text("utf-8")
            for old in ("비서실장이 실행", "비서실장만, 한 번만", "작업자에게 넘기지 않는다", "방금 승인한 명령", "그 명령을 쓰지 않는다"):
                self.assertNotIn(old, text, f"{path.name}: {old}")

    def test_worker_runs_only_the_written_approval(self):
        worker = (SKILL / "references/worker.md").read_text("utf-8")
        rule = worker.split("## 승인받은 행동")[1].split("## ")[0]
        for need in ("적힌 대상에만, 한 번만", "밖의 결과부터", "다시 본다", "다시 하지 않고 `failed`", "넓히지 않는다"):
            self.assertIn(need, rule)

    def test_chief_only_manages(self):
        """승인받은 삭제와 디스크 훑기를 본 세션이 직접 하던 일(2026-11-25)."""
        text = (SKILL / "SKILL.md").read_text("utf-8")
        self.assertRegex(text, r"\*\*관리만 한다\*\*.*승인한 것도 작업자가 한다")
        self.assertIn("턴을 끝내기 전에 셋을 본다", text)
        self.assertIn("모두 작업자가 했나?", text)
        self.assertEqual(len(re.findall(r"^- .*\?$", text.split("턴을 끝내기 전에")[1], re.M)), 3)

    def test_visible_worker_comes_first_with_permissions_on(self):
        launch = (SKILL / "references/dispatch.md").read_text("utf-8").split("## 띄우는 방법")[1].split("## ")[0]
        self.assertLess(launch.index("HERDR_ENV=1"), launch.index("subagent"))
        self.assertIn("--permission-mode auto", launch)
        self.assertNotRegex(launch, "bypassPermissions|dangerously-skip")

    def test_late_push_approval_goes_to_the_same_ship_worker(self):
        """커밋에서 멈춘 뒤 push를 승인받아도 실행자는 SKILL.md 6단계와 같다."""
        resume = (SKILL / "references/dispatch.md").read_text("utf-8").split("## 이어 시키기")[1].split("## ")[0]
        self.assertRegex(resume, "push와 PR.*비서실장은 하지 않고.*지시.*ship 작업자")

    def test_interrupted_approval_looks_outside_first(self):
        for doc in ("SKILL.md", "assets/decisions.md"):
            self.assertIn("실행 시작", (SKILL / doc).read_text("utf-8"), doc)
        skill = (SKILL / "SKILL.md").read_text("utf-8")
        self.assertRegex(skill, "그 작업자가 아직 도는지 보고, 돌면 기다린다.*밖의 결과부터")

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


def pool(used, reset_h=None, window_h=168, **more):
    return {"used": used, "reset_h": reset_h, "window_h": window_h, **more}


class Pace(unittest.TestCase):
    """한도 하나의 상태. 경계마다 하나씩."""

    def state(self, *args, **kw):
        return route.pace(route.clean(pool(*args, **kw), "x"))[0]

    def test_nothing_used_is_spare(self):
        self.assertEqual(self.state(0, 100), "spare")

    def test_95_percent_is_tight_whatever_the_pace(self):
        self.assertEqual(self.state(95, 100), "tight")
        self.assertEqual(self.state(85, 30), "tight")
        self.assertEqual(self.state(84, 10), "ok")

    def test_97_percent_counts_as_reached(self):
        self.assertEqual(self.state(96.9, 100), "tight")
        self.assertEqual(self.state(97, 100), "out")
        self.assertEqual(self.state(100, 2), "out")

    def test_fast_pace_is_tight_long_before_85(self):
        state, why = route.pace(route.clean(pool(40, 140), "x"))  # 28시간에 40% → 초기화 때 240%
        self.assertEqual(state, "tight")
        self.assertIn("42시간 뒤 닿는다", why)

    def test_slow_pace_is_spare(self):
        self.assertEqual(self.state(20, 60), "spare")   # 108시간에 20% → 초기화 때 31%
        self.assertEqual(self.state(45, 84), "ok")      # 초기화 때 90%
        self.assertEqual(self.state(50, 84), "tight")   # 초기화 때 딱 100%

    def test_just_before_reset_the_rest_is_free(self):
        self.assertEqual(self.state(90, 6), "spare")
        self.assertEqual(self.state(90, 6.5), "tight")
        self.assertEqual(self.state(98, 1), "out")

    def test_new_window_does_not_inflate_the_pace(self):
        """창이 열리고 1시간에 5%를 썼다고 840%로 늘려 잡지 않는다."""
        self.assertEqual(self.state(5, 167), "ok")
        self.assertEqual(self.state(5, 168), "ok")

    def test_unknown_values(self):
        for bad in (None, {}, {"used": None, "reset_h": 5}):
            self.assertEqual(route.pace(route.clean(bad, "x"))[0], "unknown")
        self.assertEqual(self.state(50), "ok")       # 초기화 시각을 모르면 쓴 양만 본다
        self.assertEqual(self.state(90), "tight")

    def test_impossible_reset_times_are_not_used(self):
        """astra 리뷰: 지난 초기화 시각과 창보다 긴 시각을 그대로 믿던 일."""
        for used in (30, 97, 100):
            self.assertEqual(self.state(used, -1), "unknown", used)   # 창이 이미 새로 열렸다
            self.assertEqual(self.state(used, 0), "unknown", used)
        self.assertEqual(self.state(5, 400), "ok")      # 창보다 긴 시각은 모르는 것으로
        self.assertEqual(self.state(90, 400), "tight")
        state, why = route.pace(route.clean(pool(99, 400), "x"))
        self.assertEqual(state, "out")
        self.assertNotIn("400", why)

    def test_old_reading_is_unknown_unless_already_reached(self):
        self.assertEqual(self.state(10, 100, age_h=24), "spare")
        self.assertEqual(self.state(10, 100, age_h=25), "unknown")
        self.assertEqual(self.state(99, 100, age_h=48), "out")   # 창 안에서 사용량은 줄지 않는다

    def test_wrong_shapes_are_named(self):
        for bad, where in (([85], "x이(가) 객체"), ({"used": "85"}, "x.used"), ({"used": True}, "x.used"),
                           ({"used": 101}, "x.used"), ({"used": -1}, "x.used"), ({"used": 5, "reset_h": "soon"}, "x.reset_h"),
                           ({"used": 5, "window_h": 0}, "x.window_h"), ({"used": 5, "age_h": -2}, "x.age_h"),
                           ({"used": float("nan")}, "x.used")):
            with self.assertRaises(route.BadUsage, msg=str(bad)) as caught:
                route.clean(bad, "x")
            self.assertIn(where, str(caught.exception))


OK, SPARE, TIGHT, OUT = pool(45, 84), pool(20, 60), pool(40, 140), pool(99, 100)


class PaceAge(unittest.TestCase):
    """astra 리뷰 2차: 값의 나이와 창 길이."""

    def state(self, *args, **kw):
        return route.pace(route.clean(pool(*args, **kw), "x"))[0]

    def test_window_longer_than_a_week_is_bad_input(self):
        with self.assertRaises(route.BadUsage):
            route.clean(pool(99, 400, window_h=500), "x")
        self.assertEqual(route.clean(pool(99, 100, window_h=route.MAX_WINDOW_H), "x")["left"], 100.0)

    def test_old_out_is_kept_only_when_the_window_is_known_to_be_the_same(self):
        self.assertEqual(self.state(99, 100, age_h=48), "out")       # 초기화가 아직 앞에 있다. 같은 창이다
        self.assertEqual(self.state(99, None, age_h=336), "unknown")  # 시각을 모른다. 창이 바뀌었을 수 있다
        self.assertEqual(self.state(99, None, age_h=2), "out")
        self.assertEqual(self.state(99, -1, age_h=48), "unknown")
        self.assertEqual(self.state(99, 80, age_h=336), "unknown")   # 본 때와 초기화 사이가 창보다 길다. 다른 창이다

    def test_speed_is_measured_up_to_when_the_value_was_seen(self):
        self.assertEqual(self.state(25, 132), "tight")               # 36시간에 25%
        self.assertEqual(self.state(25, 108, age_h=24), "tight")     # 같은 값을 24시간 뒤에 봐도 느려진 것이 아니다
        self.assertEqual(self.state(25, 108), "ok")                  # 방금 읽은 25%·60시간은 보통


class Route(unittest.TestCase):
    def go(self, kind="ship", level="mid", **kw):
        usage_ = {k: kw.pop(k) for k in ("claude", "fable", "codex", "cli", "mem_free_pct") if k in kw}
        return route.decide(kind, level, usage_, **kw)

    def pick(self, *args, **kw):
        r = self.go(*args, **kw)
        return (r["provider"], r["model"], r["effort"])

    def test_base_table_when_usage_is_unknown(self):
        want = {("high", "ship"): ("fable", "high"), ("high", "run"): ("fable", "high"), ("high", "scout"): ("fable", "high"),
                ("mid", "ship"): ("opus", "high"), ("mid", "run"): ("opus", "medium"), ("mid", "scout"): ("opus", "medium"),
                ("low", "ship"): ("sonnet", "medium"), ("low", "run"): ("sonnet", "medium"), ("low", "scout"): ("sonnet", "medium")}
        for (level, kind), (model, effort) in want.items():
            self.assertEqual(self.pick(kind, level), ("claude", model, effort), (level, kind))

    def test_base_table_matches_the_doc(self):
        doc = (SKILL / "references/routing.md").read_text("utf-8").split("## 기본 표")[1].split("## ")[0]
        for level in route.LEVELS:
            cells = [c.strip() for c in re.search(rf"^\| `{level}` \|(.*)\|$", doc, re.M)[1].split("|")]
            self.assertEqual(cells, [" ".join(route.BASE[level][k]) for k in route.KINDS], level)

    def test_tight_claude_keeps_only_hard_work(self):
        self.assertEqual(self.pick("ship", "mid", claude=TIGHT, codex=OK)[0], "codex")
        self.assertEqual(self.pick("scout", "low", claude=TIGHT)[0], "codex")  # Codex를 모르면 보통으로 다룬다
        self.assertEqual(self.pick("ship", "high", claude=TIGHT, codex=SPARE), ("claude", "fable", "high"))

    def test_spare_codex_takes_ordinary_work(self):
        self.assertEqual(self.pick("ship", "mid", claude=OK, codex=SPARE), ("codex", None, "high"))
        self.assertEqual(self.pick("ship", "high", claude=OK, codex=SPARE)[0], "claude")
        self.assertEqual(self.pick("ship", "mid", claude=OK, codex=OK)[0], "claude")

    def test_both_spare_stays_on_claude_and_steps_up(self):
        self.assertEqual(self.pick("run", "mid", claude=SPARE, codex=SPARE), ("claude", "opus", "high"))
        self.assertEqual(self.pick("scout", "low", claude=SPARE, codex=SPARE), ("claude", "sonnet", "high"))
        self.assertEqual(self.pick("ship", "mid", claude=SPARE, fable=SPARE), ("claude", "fable", "medium"))
        self.assertEqual(self.pick("ship", "mid", claude=SPARE, fable=OK), ("claude", "opus", "high"))

    def test_both_tight_steps_down_inside_claude(self):
        self.assertEqual(self.pick("ship", "mid", claude=TIGHT, codex=TIGHT), ("claude", "sonnet", "high"))
        self.assertEqual(self.pick("ship", "mid", claude=pool(85, 12), codex=pool(86, 12)), ("claude", "sonnet", "high"))
        self.assertEqual(self.pick("ship", "low", claude=TIGHT, codex=TIGHT), ("claude", "sonnet", "medium"))
        self.assertEqual(self.pick("ship", "mid", claude=TIGHT, without=["codex"]), ("claude", "sonnet", "high"))

    def test_fable_limit_steps_down_to_opus(self):
        for fable in (TIGHT, OUT):
            self.assertEqual(self.pick("scout", "high", claude=OK, fable=fable), ("claude", "opus", "high"))
        self.assertEqual(self.pick("scout", "high", claude=OK, fable=OK), ("claude", "fable", "high"))

    def test_reached_claude_goes_to_codex(self):
        for level in route.LEVELS:
            self.assertEqual(self.pick("ship", level, claude=OUT, codex=OK), ("codex", None, "high"), level)

    def test_one_provider_missing(self):
        self.assertEqual(self.pick("ship", "mid", claude=TIGHT, without=["codex"])[0], "claude")
        self.assertEqual(self.pick("ship", "high", without=["claude"])[0], "codex")
        self.assertEqual(self.pick("ship", "mid", cli={"claude": True, "codex": False}, claude=OK, codex=SPARE)[0], "claude")

    def test_missing_claude_cli_does_not_block_subagents(self):
        """astra 리뷰: CLI가 PATH에 없다고 호스트의 subagent 길까지 막던 일."""
        self.assertEqual(self.pick("ship", "high", cli={"claude": False, "codex": False}), ("claude", "fable", "high"))
        with self.assertRaises(route.BadUsage):
            self.go(cli=[1])

    def test_nothing_left_launches_nothing(self):
        for kw in (dict(claude=OUT, codex=OUT), dict(claude=OUT, without=["codex"]), dict(without=["claude", "codex"])):
            r = self.go("ship", "mid", mem_free_pct=60, **kw)
            self.assertIsNone(r["provider"], kw)
            self.assertIs(r["spawn"], False, kw)   # astra 리뷰: 보낼 곳이 없는데 띄워도 된다고 하던 일
            self.assertIn("기다리거나 사용자에게 묻는다", " ".join(r["why"]))

    def test_spawn_follows_memory(self):
        self.assertIs(self.go(mem_free_pct=29.9)["spawn"], False)
        self.assertIs(self.go(mem_free_pct=30)["spawn"], True)
        self.assertIsNone(self.go()["spawn"])
        for bad in ("60", True, 120):
            with self.assertRaises(route.BadUsage):
                self.go(mem_free_pct=bad)

    def test_other_eyes_means_codex(self):
        r = self.go("scout", "high", other_eyes=True, claude=SPARE, codex=TIGHT)
        self.assertEqual((r["provider"], r["role"]), ("codex", "review"))

    def test_other_eyes_without_codex_waits_for_the_user(self):
        """astra 리뷰: 다른 눈이 없는데 Claude로 띄우라고 하고 리셋권까지 묻던 일."""
        for more in ({"codex": OUT}, {"cli": {"codex": False}}, {"without": ["codex"]}):
            r = self.go("scout", "high", other_eyes=True, urgent=True, fable=OUT, mem_free_pct=60, **more)
            self.assertEqual((r["provider"], r["spawn"], r["reset"]), (None, False, None), more)
            self.assertIn("독립 리뷰가 아니다", " ".join(r["why"]))
            self.assertIn("사용자에게 묻고", " ".join(r["why"]))

    def test_memory_block_does_not_ask_for_a_reset(self):
        """astra 리뷰: 메모리가 모자라 못 띄우는데 리셋권을 묻던 일."""
        r = self.go("ship", "high", urgent=True, claude=OK, fable=OUT, mem_free_pct=18)
        self.assertEqual((r["spawn"], r["reset"]), (False, None))
        self.assertEqual(self.go("ship", "high", urgent=True, claude=OK, fable=OUT, mem_free_pct=60)["reset"], "fable")
        self.assertEqual(self.go("ship", "high", urgent=True, claude=OK, fable=OUT)["reset"], "fable")   # 메모리를 모를 때는 묻는다

    def test_cli_field_is_checked_before_use(self):
        """astra 리뷰: cli가 목록이거나 글자여도 Codex로 띄우라고 하던 일. 큰 정수에 traceback이 나던 일."""
        for bad in ({"cli": []}, {"cli": {"codex": "false"}}, {"cli": {"claude": 1}}, {"codex": pool(5, 5, window_h=10 ** 400)},
                    {"claude": pool(5, 10 ** 400)}, {"mem_free_pct": 10 ** 400}):
            with self.assertRaises(route.BadUsage, msg=str(bad)[:40]):
                self.go("scout", "mid", other_eyes=True, **bad)

    def test_explicit_null_is_not_the_same_as_missing(self):
        """astra 리뷰: cli.codex가 null인데 Codex로 띄우라고 하던 일."""
        for bad in ({"codex": None}, {"claude": None}):
            with self.assertRaises(route.BadUsage):
                route.decide("scout", "mid", {"cli": bad}, other_eyes=True)
        with self.assertRaises(route.BadUsage):
            route.decide("scout", "mid", {"cli": None}, other_eyes=True)
        self.assertEqual(route.decide("scout", "mid", {"cli": {}}, other_eyes=True)["provider"], "codex")

    def test_low_memory_never_asks_for_a_reset(self):
        """astra 리뷰: 보낼 곳도 없고 메모리도 모자란데 리셋권을 묻던 일."""
        r = self.go("ship", "high", urgent=True, claude=pool(99, 80), without=["codex"], mem_free_pct=18)
        self.assertEqual((r["provider"], r["spawn"], r["reset"]), (None, False, None))
        self.assertEqual(self.go("ship", "high", urgent=True, claude=pool(99, 80), without=["codex"], mem_free_pct=60)["reset"], "weekly")

    def test_time_since_the_snapshot_counts(self):
        """astra 리뷰: 30분 전에 읽은 '15분 뒤 초기화'를 지금도 닿음으로 보던 일."""
        r = route.decide("ship", "mid", {"codex": pool(99, 0.25), "claude": pool(99, 100)}, elapsed_h=0.5)
        self.assertEqual((r["state"]["codex"], r["state"]["claude"]), ("unknown", "out"))
        self.assertEqual(route.clean(pool(10, 100, age_h=2), "x", 0.5), {"used": 10.0, "left": 99.5, "window": 168.0, "age": 2.5})

    def test_another_claude_model_when_the_user_accepts_one(self):
        """astra 리뷰: 다른 Claude 모델로 보자고 했는데 만든 모델을 다시 고르던 일."""
        pick = lambda **kw: self.pick("scout", "high", **kw)  # noqa: E731
        self.assertEqual(pick(not_model="fable"), ("claude", "opus", "high"))
        self.assertEqual(pick(not_model="opus"), ("claude", "fable", "high"))
        self.assertEqual(pick(not_model="opus", fable=OUT), ("claude", "sonnet", "high"))    # fable이 닿아 opus로 내려온 뒤
        self.assertEqual(self.pick("scout", "low", not_model="sonnet"), ("claude", "opus", "high"))
        self.assertIn("fable이 만든 것을 보는 일", " ".join(self.go("scout", "high", not_model="fable")["why"]))
        r = self.go("scout", "high", urgent=True, not_model="fable", claude=OK, fable=OUT)
        self.assertEqual((r["model"], r["reset"]), ("opus", None))   # 쓰지 않을 모델의 리셋권은 묻지 않는다

    def test_no_claude_cli_means_subagent_only(self):
        """astra 리뷰: Claude CLI가 없는데 herdr 세션으로 띄우는 것처럼 답하던 일."""
        self.assertEqual(self.go("ship", "high", cli={"claude": False, "codex": True})["how"], "subagent")
        self.assertIsNone(self.go("ship", "high", cli={"claude": True, "codex": True})["how"])
        self.assertIsNone(self.go("ship", "mid", cli={"claude": False, "codex": True}, claude=TIGHT)["how"])   # Codex로 간다

    def test_reset_is_asked_only_when_urgent_reached_and_far(self):
        ask = lambda **kw: self.go(kw.pop("kind", "ship"), kw.pop("level", "high"), **kw)["reset"]  # noqa: E731
        self.assertEqual(ask(urgent=True, claude=OK, fable=OUT), "fable")
        self.assertIsNone(ask(urgent=False, claude=OK, fable=OUT))
        self.assertIsNone(ask(urgent=True, claude=OK, fable=pool(99, 23)))    # 곧 초기화된다
        self.assertIsNone(ask(urgent=True, claude=OK, fable=pool(99, 24)))    # 딱 24시간은 '넘게'가 아니다
        self.assertEqual(ask(urgent=True, claude=OK, fable=pool(99, 24.5)), "fable")
        self.assertIsNone(ask(urgent=True, claude=OK, fable=pool(99)))        # 초기화 시각을 모른다
        self.assertIsNone(ask(urgent=True, claude=OK, fable=pool(99, 400)))   # 있을 수 없는 시각
        self.assertIsNone(ask(urgent=True, claude=OK, fable=TIGHT))           # 아직 닿지 않았다
        self.assertIsNone(ask(urgent=True, level="mid", claude=OK, fable=OUT))  # Fable이 필요한 일이 아니다
        self.assertEqual(ask(urgent=True, claude=OUT, codex=OUT), "weekly")
        self.assertEqual(ask(urgent=True, level="mid", claude=OUT, codex=OUT), "weekly")
        self.assertIsNone(ask(urgent=True, level="mid", claude=OUT, codex=OK))  # Codex로 갈 수 있다
        self.assertEqual(ask(urgent=True, level="high", claude=OUT, codex=OK), "weekly")
        self.assertIsNone(ask(urgent=True, claude=pool(99, 5), codex=OUT))
        self.assertIsNone(ask(urgent=True, without=["claude"], fable=OUT))

    def test_independent_review_never_asks_for_a_reset(self):
        """astra 리뷰: Codex로 가는 독립 리뷰인데 Claude 리셋권을 묻던 일."""
        for kw in (dict(claude=OK, fable=OUT), dict(claude=OUT)):
            r = self.go("scout", "high", urgent=True, other_eyes=True, codex=SPARE, **kw)
            self.assertEqual((r["provider"], r["reset"]), ("codex", None), kw)

    def test_every_answer_has_a_reason(self):
        for kind in route.KINDS:
            for level in route.LEVELS:
                for claude in (None, OK, SPARE, TIGHT, OUT):
                    for codex in (None, SPARE, TIGHT, OUT):
                        r = self.go(kind, level, claude=claude, codex=codex)
                        self.assertTrue(r["why"], (kind, level))
                        self.assertIn(r["provider"], ("claude", "codex", None))
                        if r["provider"] == "claude":
                            self.assertIn(r["model"], ("fable", "opus", "sonnet"))
                            self.assertIn(r["effort"], ("medium", "high"))


class RouteCli(Base):
    def run_route(self, *args, usage_=None, stdin=None):
        if usage_ is not None:
            (self.home / "usage.json").write_text(json.dumps(usage_), "utf-8")
            args = (*args, "--usage", str(self.home / "usage.json"))
        return subprocess.run([sys.executable, "-I", str(SKILL / "scripts/route.py"), "--home", str(self.home), *args],
                              capture_output=True, text=True, encoding="utf-8", input=stdin, timeout=30)

    def args_line(self, *args):
        return re.search(r"^띄울 때 붙일 인자: (.*)$", self.run_route(*args).stdout, re.M)[1]

    def test_text_output_has_what_the_brief_needs(self):
        out = self.run_route("--kind", "ship", "--level", "high", usage_={"mem_free_pct": 55}).stdout
        self.assertIn("보낼 곳: claude · fable · effort high", out)
        self.assertIn("brief의 model: claude fable high", out)
        self.assertIn("띄울 때 붙일 인자: --model fable --effort high", out)
        self.assertIn("띄워도 되나: 예. 빈 메모리 55%", out)
        self.assertIn("리셋권: 묻지 않는다", out)

    def test_codex_args_keep_sandbox_and_approvals_on(self):
        for kind, tail in (("ship", "--approve-for-me --add-dir '<상태>/tasks/<id>/out'"), ("run", "-a on-request --add-dir '<상태>/tasks/<id>/out'"),
                           ("scout", "-a on-request -C '<상태>/tasks/<id>/out'")):
            line = self.args_line("--kind", kind, "--level", "mid", "--without", "claude")
            self.assertEqual(line, "-c 'model_reasoning_effort=\"high\"' -s workspace-write " + tail
                             + " (미리보기: --task <id>를 줘야 실제 경로가 나온다)", kind)
            self.assertNotRegex(line, "dangerously|danger-full-access|never")

    def test_codex_never_gets_the_folder_that_holds_the_brief(self):
        """astra 리뷰: 승인 원문과 checked가 든 brief.md까지 Codex가 쓸 수 있던 일. 여는 곳은 결과 폴더(out)뿐이다."""
        for kind in route.KINDS:
            data = json.loads(self.run_route("--kind", kind, "--level", "low", "--without", "claude", "--task", "pay-fix", "--json").stdout)
            opened = [data["launch"][i + 1] for i, a in enumerate(data["launch"]) if a in ("--add-dir", "-C")]
            self.assertEqual(opened, [f"{self.home}/tasks/pay-fix/out"], kind)
            self.assertIs(data["preview"], False)
        out = self.run_route("--kind", "scout", "--level", "low", "--without", "claude", "--task", "pay-fix").stdout
        self.assertIn("Codex 결과 자리: 인자에 든 결과 폴더(tasks/<id>/out)", out)
        self.assertNotIn("미리보기", out)
        self.assertIs(json.loads(self.run_route("--kind", "scout", "--level", "low", "--without", "claude", "--json").stdout)["preview"], True)

    def test_state_folder_inside_what_codex_can_write_stops_the_launch(self):
        """astra 리뷰: 상태 폴더가 임시 폴더 아래면 brief도 Codex의 쓰기 범위에 들던 일."""
        temp = os.path.realpath(tempfile.gettempdir())
        self.assertIn("임시 폴더", route.codex_can_write(f"{temp}/state/tasks/x", None))
        other_case = str(self.home).upper()   # 대소문자를 가리지 않는 파일 시스템에서는 같은 폴더다
        if other_case != str(self.home) and os.path.exists(other_case):
            self.assertIn("임시 폴더", route.codex_can_write(f"{other_case}/tasks/x", None))
        linked = self.home / "tasks" / "linked"   # 결과 폴더가 작업 폴더를 가리키는 링크
        linked.mkdir(parents=True)
        (linked / "out").symlink_to(linked)
        self.assertIn("결과 폴더(링크)", route.codex_can_write(str(linked), None))
        self.assertIn("임시 폴더", route.codex_can_write("/tmp/state/tasks/x", "/opt/proj"))
        self.assertIsNone(route.codex_can_write("/opt/chief-state/tasks/x", None))
        self.assertIsNone(route.codex_can_write("/opt/chief-state/tasks/x", "/opt/proj"))
        self.assertIn("작업 공간", route.codex_can_write("/opt/proj/.state/tasks/x", "/opt/proj"))
        self.assertIsNone(route.codex_can_write("/opt/project-b/tasks/x", "/opt/proj"))   # 이름만 비슷한 옆 폴더
        data = json.loads(self.run_route("--kind", "ship", "--level", "high", "--urgent", "--task", "t1", "--without", "claude", "--json",
                                         usage_={"claude": OUT, "mem_free_pct": 60}).stdout)   # 시험의 상태 폴더는 임시 폴더다
        self.assertEqual((data["provider"], data["spawn"], data["reset"]), ("codex", False, None))
        self.assertIn("Codex 작업자가 brief를 쓸 수 있다", data["spawn_why"])
        claude = json.loads(self.run_route("--kind", "ship", "--level", "high", "--json", usage_={"mem_free_pct": 60}).stdout)
        self.assertIs(claude["spawn"], True)   # Claude 작업자는 그대로다

    def test_codex_ship_needs_the_workspace_to_check_it(self):
        """astra 리뷰: 작업 공간을 주지 않으면 그 안의 상태 폴더를 못 잡던 일."""
        keep = route.temp_roots
        self.addCleanup(setattr, route, "temp_roots", keep)
        route.temp_roots = lambda: []   # 시험의 상태 폴더가 임시 폴더라 그 검사는 끈다
        usage_file = self.home / "u.json"
        usage_file.write_text('{"mem_free_pct": 60}', "utf-8")
        import contextlib
        import io

        def ask(*more):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                route.main(["--home", str(self.home), "--level", "mid", "--without", "claude", "--usage", str(usage_file), "--json", *more])
            return json.loads(buf.getvalue())
        self.assertIn("--workspace <작업 공간>을 줘야", ask("--kind", "ship", "--task", "t1")["spawn_why"])
        self.assertIs(ask("--kind", "ship", "--task", "t1", "--workspace", "/opt/proj")["spawn"], True)
        self.assertIn("작업 공간 안", ask("--kind", "run", "--task", "t1", "--workspace", str(self.home))["spawn_why"])
        self.assertIs(ask("--kind", "scout", "--task", "t1")["spawn"], True)    # scout는 결과 폴더에서 뜬다
        self.assertIs(ask("--kind", "ship")["spawn"], True)                     # 미리보기

    def test_snapshot_age_moves_the_reset_closer(self):
        out = self.run_route("--kind", "ship", "--level", "mid", "--now", "2026-01-10T12:00:00+09:00", "--json",
                             usage_={"at": "2026-01-10T11:30+09:00", "codex": pool(99, 0.25), "mem_free_pct": 60}).stdout
        self.assertEqual(json.loads(out)["state"]["codex"], "unknown")

    def test_not_model_flag(self):
        out = self.run_route("--kind", "scout", "--level", "high", "--not-model", "fable").stdout
        self.assertIn("보낼 곳: claude · opus · effort high", out)
        self.assertIn("--not-model <만든 모델>", self.run_route("--kind", "scout", "--level", "high", "--other-eyes", "--without", "codex").stdout)

    def test_other_eyes_is_not_a_ship(self):
        """astra 리뷰: 독립 리뷰에 ship의 쓰기·자동 승인 인자가 붙던 일."""
        proc = self.run_route("--kind", "ship", "--level", "mid", "--other-eyes")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertIn("--other-eyes는 scout와 run에만", proc.stderr)

    def test_old_snapshot_is_refused(self):
        """astra 리뷰: 오래전에 읽은 사용량과 메모리로 띄워도 된다고 하던 일."""
        ask = lambda at: self.run_route("--kind", "ship", "--level", "high", "--urgent", "--now", "2026-01-10T12:00:00+09:00",  # noqa: E731
                                        usage_={"at": at, "claude": OUT, "mem_free_pct": 60})
        self.assertEqual(ask("2026-01-10T11:30+09:00").returncode, 0)
        self.assertEqual(ask("2026-01-10T02:30+00:00").returncode, 0)   # 다른 시간대로 적힌 같은 때
        for at in ("2020-01-01T00:00+09:00", "2026-01-10T10:59+09:00", "2026-01-10T13:00+09:00", "어제", 5):
            proc = ask(at)
            self.assertNotEqual(proc.returncode, 0, at)
            self.assertEqual(proc.stdout, "")
            self.assertIn("route.py: 사용량을 읽지 못함", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_no_claude_cli_is_said_in_the_text(self):
        out = self.run_route("--kind", "ship", "--level", "high", usage_={"cli": {"claude": False, "codex": True}}).stdout
        self.assertIn("띄우는 방식: 호스트의 Claude subagent만", out)
        self.assertNotIn("띄우는 방식", self.run_route("--kind", "ship", "--level", "high").stdout)

    def test_codex_scout_can_write_only_its_task_folder(self):
        """astra 리뷰: scout에게 프로젝트 쓰기까지 열어 주던 일. -C는 결과 폴더만 쓸 수 있게 한다."""
        line = self.args_line("--kind", "scout", "--level", "low", "--other-eyes", "--task", "pay-fix")
        self.assertTrue(line.endswith(f"-a on-request -C {self.home}/tasks/pay-fix/out"), line)
        self.assertNotIn("--add-dir", line)
        self.assertNotIn("--approve-for-me", line)

    def test_task_id_becomes_a_real_path_and_bad_ids_stop(self):
        self.assertTrue(self.args_line("--kind", "ship", "--level", "mid", "--without", "claude", "--task", "pay-fix")
                        .endswith(f"--approve-for-me --add-dir {self.home}/tasks/pay-fix/out"))
        rel = subprocess.run([sys.executable, "-I", str(SKILL / "scripts/route.py"), "--home", "state", "--kind", "scout", "--level", "low",
                              "--without", "claude", "--task", "t1"], capture_output=True, text=True, encoding="utf-8", cwd=self.home)
        self.assertIn(f"-C {os.path.realpath(self.home)}/state/tasks/t1/out", rel.stdout)   # 상대 경로로 줘도 절대 경로로 낸다
        for bad in ("../x", "a b", "A", "-x", ""):
            proc = self.run_route("--kind", "ship", "--level", "mid", "--task", bad)
            if bad:
                self.assertNotEqual(proc.returncode, 0, bad)
                self.assertEqual(proc.stdout, "")

    def test_codex_model_comes_from_the_state_folder(self):
        (self.home / "routing.json").write_text('{"codex_model": "build-x", "codex_review_model": "review y"}', "utf-8")
        self.assertTrue(self.args_line("--kind", "ship", "--level", "mid", "--without", "claude").startswith("-m build-x -c "))
        out = self.run_route("--kind", "scout", "--level", "mid", "--other-eyes").stdout
        self.assertIn("보낼 곳: codex · review y · effort high", out)
        self.assertIn("인자: -m 'review y' -c ", out)   # 빈칸이 든 이름이 두 인자로 갈라지지 않는다
        data = json.loads(self.run_route("--kind", "scout", "--level", "mid", "--other-eyes", "--json").stdout)
        self.assertEqual((data["model"], data["launch"][:2]), ("review y", ["-m", "review y"]))
        (self.home / "routing.json").write_text('{"codex_model": ["x"]}', "utf-8")
        self.assertNotEqual(self.run_route("--kind", "ship", "--level", "mid", "--without", "claude").returncode, 0)

    def test_low_memory_says_do_not_launch(self):
        ask = lambda mem: self.run_route("--kind", "run", "--level", "low", usage_={"mem_free_pct": mem}).stdout  # noqa: E731
        self.assertIn("띄워도 되나: 아니오. 빈 메모리 29% < 30%", ask(29))
        for mem in (29.96, 29.999):   # astra 리뷰: 반올림해 30%로 보이던 일. 표시는 내림한다
            self.assertIn("띄워도 되나: 아니오. 빈 메모리 29.9% < 30%", ask(mem))
        self.assertIn("띄워도 되나: 예", ask(30))
        self.assertIn("띄워도 되나: 빈 메모리를 읽지 못함", ask(None))

    def test_reset_is_a_question_never_an_action(self):
        out = self.run_route("--kind", "ship", "--level", "high", "--urgent",
                             usage_={"claude": OK, "fable": OUT}).stdout
        self.assertIn("보낼 곳: claude · opus · effort high", out)
        self.assertIn("리셋권: Fable 리셋권을 쓸지 사용자에게 묻는다. 쓰지 않고 묻기만 한다", out)

    def test_nothing_left(self):
        out = self.run_route("--kind", "ship", "--level", "mid", usage_={"claude": OUT, "codex": OUT, "mem_free_pct": 60}).stdout
        self.assertIn("보낼 곳: 없음. 띄우지 않는다", out)
        self.assertIn("띄워도 되나: 아니오. 보낼 곳이 없다", out)
        self.assertNotIn("띄울 때 붙일 인자", out)
        data = json.loads(self.run_route("--kind", "ship", "--level", "mid", "--json", "--without", "claude", "--without", "codex",
                                         usage_={"mem_free_pct": 60}).stdout)
        self.assertEqual((data["provider"], data["spawn"], data["launch"]), (None, False, []))

    def test_usage_from_stdin_and_json_out(self):
        proc = self.run_route("--kind", "ship", "--level", "mid", "--usage", "-", "--json",
                              stdin=json.dumps({"claude": TIGHT, "codex": SPARE, "mem_free_pct": 12}))
        data = json.loads(proc.stdout)
        self.assertEqual((data["provider"], data["effort"], data["spawn"]), ("codex", "high", False))
        self.assertEqual(data["state"], {"claude": "tight", "fable": "unknown", "codex": "spare"})

    def test_broken_usage_stops_instead_of_guessing(self):
        for bad in ("{", "[1, 2]", "", '{"claude": [85]}', '{"codex": {"used": "many"}}', '{"mem_free_pct": "a"}'):
            proc = self.run_route("--kind", "ship", "--level", "mid", "--usage", "-", stdin=bad)
            self.assertNotEqual(proc.returncode, 0, bad)
            self.assertIn("route.py: 사용량", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(proc.stdout, "")
        proc = self.run_route("--kind", "ship", "--level", "mid", "--usage", str(self.home / "none.json"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(str(self.home), proc.stderr)   # 경로를 오류에 옮기지 않는다
        self.assertIn("claude.used", self.run_route("--kind", "ship", "--level", "mid", "--usage", "-",
                                                    stdin='{"claude": {"used": 300}}').stderr)


NOW = dt.datetime.fromisoformat("2026-01-10T12:00:00+09:00")  # 서머타임이 없는 시간대로 시험한다
SCREEN = """
  Current week (all models)
  \x1b[38;2;1;2;3m█████████\x1b[0m                         61% used
  Resets Jan 12 at 2:59am (Asia/Seoul)

  Current week (Fable)
  ██                                   8% used
  Resets Jan 12 at 2:59am (Asia/Seoul)

  Opus | 11% | 5h -- | 7d 42% (3d5h)
"""


class Usage(Base):
    def test_status_line(self):
        claude, fable = usage.parse_claude("  Opus | 11% | 5h 3% (2h1m) | 7d 42% (3d5h)      o low\n", NOW)
        self.assertEqual((claude["used"], claude["reset_h"], claude["from"]), (42.0, 77.0, "상태 줄"))
        self.assertIsNone(fable)
        self.assertEqual(usage.parse_claude("x | 5h -- | 7d 9% (45m)", NOW)[0]["reset_h"], 0.75)
        self.assertEqual(usage.parse_claude("x | 5h -- | 7d 9% (3h20m) | y", NOW)[0]["reset_h"], 3.33)
        self.assertIsNone(usage.parse_claude("x | 5h -- | 7d 9%", NOW)[0]["reset_h"])
        self.assertIsNone(usage.parse_claude("x | 5h -- | 7d 9% (soon)", NOW)[0]["reset_h"])

    def test_no_value_is_none_not_zero(self):
        for text in ("", "Opus | 5h -- | 7d --", "x | 5h -- | 7d 250% (1d)", "weekly 97% left"):
            self.assertEqual(usage.parse_claude(text, NOW), (None, None), text)

    def test_prose_is_not_a_status_line(self):
        """astra 리뷰: 본문의 '7d 5%'를 상태 줄로 읽던 일."""
        for text in ("보고서의 예시는 7d 5% 입니다", "지난 7d 30% 늘었다", "x | 5h -- | 7d 5%입니다", "x | 17d 5% (1d)"):
            self.assertEqual(usage.parse_claude(text, NOW), (None, None), text)

    def test_last_status_line_wins(self):
        self.assertEqual(usage.parse_claude("a | 5h -- | 7d 10% (6d)\n...\na | 5h -- | 7d 12% (5d23h)\n", NOW)[0]["used"], 12.0)

    def test_usage_screen_has_fable_and_wins_over_status_line(self):
        claude, fable = usage.parse_claude(SCREEN, NOW)
        self.assertEqual((claude["used"], claude["from"]), (61.0, "/usage 화면"))
        self.assertEqual(fable["used"], 8.0)
        self.assertEqual(claude["reset_h"], 38.98)
        self.assertEqual(fable["reset_h"], 38.98)

    def test_usage_bar_reads_the_whole_number(self):
        """astra 리뷰: '10.5% used'에서 5만 읽던 일."""
        claude, _ = usage.parse_claude("Current week (all models)\n ██ 10.5% used\n", NOW)
        self.assertEqual((claude["used"], claude["reset_h"]), (10.5, None))
        self.assertIsNone(usage.parse_claude("Current week (all models)\n ██ 1000% used\n", NOW)[0])

    def test_reset_text(self):
        hours = lambda text, now=NOW: usage.reset_hours(text, now)  # noqa: E731
        self.assertEqual(hours("Jan 12 at 2:59am (Asia/Seoul)"), 38.98)
        self.assertEqual(hours("Jan 12 at 3pm (UTC)"), 60.0)          # 다른 시간대
        self.assertEqual(hours("2:59am (Asia/Seoul)"), 14.98)         # 날짜 없이 시각만
        self.assertEqual(hours("12pm (Asia/Seoul)"), 0.0)
        self.assertEqual(hours("Jan 2 at 1am (Asia/Seoul)", dt.datetime.fromisoformat("2026-12-30T01:00:00+09:00")), 72.0)
        for bad in ("", "soon", "Jan 12 at 2:59am (Mars/Olympus)", "Foo 12 at 2:59am", "Feb 31 at 1am"):
            self.assertIsNone(hours(bad), bad)

    def test_old_screen_is_not_read_as_next_year(self):
        """astra 리뷰: 지난 날짜를 내년으로 넘겨 8천 시간 뒤로 읽던 일."""
        self.assertIsNone(usage.reset_hours("Jan 8 at 12pm (UTC)", NOW))
        self.assertIsNone(usage.reset_hours("Dec 28 at 12pm (UTC)", dt.datetime.fromisoformat("2026-12-30T12:00:00+00:00")))
        self.assertIsNone(usage.reset_hours("Mar 1 at 12pm (UTC)", NOW))   # 주간 창보다 먼 시각

    def test_screen_whose_reset_has_passed_is_an_old_window(self):
        """astra 리뷰: 초기화가 지난 화면의 99%를 지금 창의 '닿음'으로 읽던 일."""
        for used in (40, 99):
            claude, fable = usage.parse_claude(f"Current week (all models)\n ██ {used}% used\n Resets Jan 8 at 12pm (UTC)\n"
                                               f"Current week (Fable)\n ██ {used}% used\n Resets Jan 9 at 12pm (UTC)\n", NOW)
            self.assertEqual((claude, fable), (None, None))
        claude, _ = usage.parse_claude("Current week (all models)\n ██ 99% used\n Resets Jan 8 at 12pm\n", NOW)
        self.assertIsNone(claude)   # 시간대 이름이 없어도 어느 시간대로 보나 지난 날짜다
        claude, _ = usage.parse_claude("Current week (all models)\n ██ 99% used\n Resets Jan 10 at 3pm\n", NOW)
        self.assertEqual((claude["used"], claude["reset_h"]), (99.0, None))
        claude, _ = usage.parse_claude("Current week (all models)\n ██ 40% used\n Resets Mar 1 at 12pm (UTC)\n", NOW)
        self.assertEqual((claude["used"], claude["reset_h"]), (40.0, None))   # 먼 앞날은 시각만 모르는 것으로 둔다

    def test_text_that_only_looks_like_a_reading_is_not_read(self):
        """astra 리뷰: 본문의 `|`와 음수 막대를 사용량으로 읽던 일."""
        for text in ("보고서 예시 | 7d 5% 입니다\n", "보고서 예시 | 7d 5%  입니다\n", "x | 7d 5% (3d5h)\n", "보고서 예시 | 5h 설명 | 7d 5%  입니다\n", "a | 5h -- | 7d 5%입니다\n", "x | 5h -- | 7d 5% (3d5h) 남음\n",
                     "Current week (all models)\n ██ -1% used\n"):
            self.assertEqual(usage.parse_claude(text, NOW), (None, None), text)
        for text in ("  Opus | 11% | 5h -- | 7d 42% (3d5h)\n", "  Opus | 5h -- | 7d 42% (3d5h) | x\n", "  Opus | 5h -- | 7d 42% (3d5h)      o low\n", "  Opus | 5h -- | 7d 42%\n"):
            self.assertEqual(usage.parse_claude(text, NOW)[0]["used"], 42.0, text)

    def test_times_that_do_not_exist_are_not_read(self):
        """astra 리뷰: 13pm과 서머타임이 건너뛰는 시각을 받던 일."""
        noon = dt.datetime.fromisoformat("2026-01-10T12:00:00+00:00")
        for bad in ("13pm (UTC)", "0am (UTC)", "Jan 10 at 13pm (UTC)", "Jan 10 at 3pm", "3pm"):   # 시간대 이름이 없으면 짐작하지 않는다
            self.assertIsNone(usage.reset_hours(bad, noon), bad)
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("America/New_York")
        before = dt.datetime(2026, 3, 8, 1, 0, tzinfo=zone)
        if before.utcoffset() == dt.datetime(2026, 3, 8, 4, 0, tzinfo=zone).utcoffset():
            self.skipTest("이 기계의 시간대 자료에는 그날 서머타임 전환이 없다")
        self.assertIsNone(usage.reset_hours("Mar 8 at 2:30am (America/New_York)", before))
        self.assertIsNone(usage.reset_hours("Mar 8 at 2:30am", before))
        self.assertEqual(usage.reset_hours("Mar 8 at 3:30am (America/New_York)", before), 1.5)

    def rollout(self, name, *events, day="2026/01/10", pad=0):
        folder = self.home / "sessions" / day
        folder.mkdir(parents=True, exist_ok=True)
        lines = ["not json", json.dumps({"type": "event_msg", "payload": {"type": "other"}})]
        for stamp, limits in events:
            lines.append(json.dumps({"timestamp": stamp, "type": "event_msg",
                                     "payload": {"type": "token_count", "rate_limits": limits}}))
        lines += [json.dumps({"type": "output", "text": "x" * 9_999})] * pad
        path = folder / f"rollout-{name}.jsonl"
        path.write_text("\n".join(lines) + "\n", "utf-8")
        return path

    def week(self, used, left_h, minutes=10080, **more):
        return {"primary": {"used_percent": used, "window_minutes": minutes, "resets_at": int(NOW.timestamp() + left_h * 3600)},
                "secondary": None, "plan_type": "x", "credits": {"balance": "1"}, **more}

    def test_codex_latest_event_wins(self):
        self.rollout("a", ("2026-01-10T01:00:00.000Z", self.week(11, 100)), ("2026-01-10T02:00:00.000Z", self.week(12, 99)))
        self.rollout("b", ("2026-01-10T02:30:00.000Z", self.week(14, 98.5)))
        got, why = usage.read_codex(self.home, NOW)
        self.assertIsNone(why)
        self.assertEqual((got["used"], got["reset_h"], got["window_h"], got["age_h"]), (14.0, 98.5, 168.0, 0.5))
        self.assertEqual(set(got), {"used", "reset_h", "window_h", "age_h", "from"})  # 잔액·요금제는 옮기지 않는다

    def test_codex_only_the_weekly_window_of_the_base_limit(self):
        """astra 리뷰: 가장 긴 창을 무조건 주간으로, 다른 한도의 값도 기본값으로 읽던 일."""
        limits = self.week(70, 2, minutes=300)
        limits["secondary"] = {"used_percent": 20, "window_minutes": 10080, "resets_at": int(NOW.timestamp() + 50 * 3600)}
        self.rollout("a", ("2026-01-10T02:00:00Z", limits))
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 20.0)
        self.rollout("b", ("2026-01-10T02:10:00Z", self.week(99, 2, minutes=300)))       # 5시간 창만 있는 기록
        self.rollout("c", ("2026-01-10T02:20:00Z", self.week(88, 50, limit_id="other")))  # 다른 한도
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 20.0)

    def test_codex_five_hour_only_is_not_weekly(self):
        self.rollout("a", ("2026-01-10T02:00:00Z", self.week(99, 2, minutes=300)))
        self.assertEqual(usage.read_codex(self.home, NOW), (None, "codex-no-weekly-limit"))

    def test_codex_window_reset_since_last_seen_is_unknown(self):
        """astra 리뷰: 초기화가 지났다고 0%를 지어내던 일."""
        self.rollout("a", ("2026-01-01T02:00:00Z", self.week(88, -30)))
        self.assertEqual(usage.read_codex(self.home, NOW), (None, "codex-window-reset-since-last-seen"))

    def test_codex_old_reading_keeps_its_age(self):
        self.rollout("a", ("2026-01-08T03:00:00Z", self.week(10, 100)))
        got, _ = usage.read_codex(self.home, NOW)
        self.assertEqual(got["age_h"], 48.0)
        self.assertEqual(route.decide("ship", "mid", {"codex": got})["state"]["codex"], "unknown")

    def test_codex_weekly_means_exactly_seven_days(self):
        """astra 리뷰: 6일 창의 99%를 주간으로 읽던 일."""
        limits = self.week(99, 50, minutes=8640)
        limits["secondary"] = {"used_percent": 12, "window_minutes": 10080, "resets_at": int(NOW.timestamp() + 50 * 3600)}
        self.rollout("a", ("2026-01-10T02:00:00Z", limits))
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 12.0)

    def test_codex_reading_from_the_future_is_ignored(self):
        """astra 리뷰: 시계가 틀린 앞날의 기록이 가장 새 값이 되던 일."""
        self.rollout("a", ("2026-01-10T02:00:00Z", self.week(7, 100)))
        self.rollout("b", ("2026-01-12T03:00:00Z", self.week(99, 100)))
        got, _ = usage.read_codex(self.home, NOW)
        self.assertEqual((got["used"], got["age_h"]), (7.0, 1.0))

    def test_codex_newer_reading_in_an_older_file_wins(self):
        """astra 리뷰: 늦게 닫힌 기록의 옛 값에서 멈추던 일."""
        late = self.rollout("late", ("2026-01-10T00:00:00Z", self.week(2, 100)))
        early = self.rollout("early", ("2026-01-10T02:00:00Z", self.week(99, 100)))
        os.utime(early, (late.stat().st_mtime - 60,) * 2)
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 99.0)

    def test_codex_unchecked_file_that_may_be_newer_means_unknown(self):
        """astra 리뷰: 다 못 본 기록이 있는데 옛 값을 최신으로 내던 일."""
        late = self.rollout("late", ("2026-01-10T00:00:00Z", self.week(2, 100)))
        early = self.rollout("early", ("2026-01-10T02:00:00Z", self.week(99, 100)), pad=250)
        os.utime(early, (late.stat().st_mtime - 60,) * 2)
        for name, value in (("SCAN_BYTES", usage.CHUNK), ("SCAN_FILES", 1)):
            keep = getattr(usage, name)
            setattr(usage, name, value)
            try:
                self.assertEqual(usage.read_codex(self.home, NOW), (None, "codex-scan-limit"), name)
            finally:
                setattr(usage, name, keep)
        self.assertEqual(usage.last_weekly(self.home / "sessions" / "none.jsonl", NOW), "limit")   # 못 읽은 기록
        os.utime(early, (1, 1))   # 가장 새 값을 본 때보다 먼저 닫힌 기록은 보지 않아도 된다
        usage.SCAN_FILES, keep = 1, usage.SCAN_FILES
        self.addCleanup(setattr, usage, "SCAN_FILES", keep)
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 2.0)

    def test_codex_clock_slack_also_applies_when_skipping_files(self):
        """astra 리뷰: 허용한 시계 차이 안의 더 새 기록을 건너뛰던 일."""
        late = self.rollout("late", ("2026-01-10T03:01:00Z", self.week(2, 100)))
        early = self.rollout("early", ("2026-01-10T03:02:00Z", self.week(99, 100)))
        os.utime(late, (NOW.timestamp(),) * 2)
        os.utime(early, (NOW.timestamp() - 1,) * 2)
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 99.0)

    def test_codex_missing_or_broken_records(self):
        self.assertEqual(usage.read_codex(self.home / "nope", NOW), (None, "codex-no-sessions"))
        self.rollout("a")
        self.rollout("b", ("2026-01-10T02:00:00Z", {"primary": None, "secondary": None}))
        self.rollout("c", ("bad stamp", self.week(5, 5)))
        self.rollout("d", ("2026-01-10T02:00:00Z", [1]))                       # 객체가 아닌 값
        self.rollout("e", ("2026-01-10T02:00:00", self.week(5, 5)))            # 시간대 없는 시각
        self.rollout("f", ("2026-01-10T02:00:00Z", self.week("many", 5)))
        self.rollout("g", ("2026-01-10T02:00:00Z", self.week(True, 5)))
        self.assertEqual(usage.read_codex(self.home, NOW), (None, "codex-no-weekly-limit"))

    def test_codex_event_before_a_long_output_is_still_found(self):
        """astra 리뷰: 꼬리 40만 바이트만 읽어 더 옛 값을 최신으로 내던 일."""
        old = self.rollout("old", ("2026-01-10T01:00:00Z", self.week(2, 100)))
        new = self.rollout("new", ("2026-01-10T02:00:00Z", self.week(91, 99)), pad=250)   # 약 2.5MB가 뒤따른다
        os.utime(old, (1, 1))
        self.assertGreater(new.stat().st_size, 2 * usage.CHUNK)
        self.assertEqual(usage.read_codex(self.home, NOW)[0]["used"], 91.0)

    def test_codex_scan_limit_does_not_fall_back_to_an_older_value(self):
        old = self.rollout("old", ("2026-01-10T01:00:00Z", self.week(2, 100)))
        self.rollout("new", ("2026-01-10T02:00:00Z", self.week(91, 99)), pad=250)
        os.utime(old, (1, 1))
        keep = usage.SCAN_BYTES
        self.addCleanup(setattr, usage, "SCAN_BYTES", keep)
        usage.SCAN_BYTES = usage.CHUNK
        self.assertEqual(usage.read_codex(self.home, NOW), (None, "codex-scan-limit"))

    def run_usage(self, *args):
        return subprocess.run([sys.executable, "-I", str(SKILL / "scripts/usage.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_cli_feeds_route(self):
        (self.home / "screen.txt").write_text(SCREEN, "utf-8")
        self.rollout("a", ("2026-01-10T02:00:00Z", self.week(3, 120)))
        proc = self.run_usage("--claude-screen", str(self.home / "screen.txt"), "--codex-home", str(self.home), "--now", NOW.isoformat())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(set(data), {"at", "cli", "claude", "fable", "codex", "mem_free_pct", "notes"})
        self.assertEqual((data["claude"]["used"], data["fable"]["used"], data["codex"]["used"], data["notes"]), (61.0, 8.0, 3.0, []))
        data["cli"] = {"claude": True, "codex": True}   # 시험하는 기계에 CLI가 있든 없든 같은 답
        r = route.decide("ship", "mid", data)
        self.assertEqual((r["state"]["claude"], r["state"]["codex"], r["provider"]), ("ok", "spare", "codex"))

    def test_cli_without_any_source_gives_nulls_and_fixed_words(self):
        """astra 리뷰: 오류 원문과 경로를 notes에 옮기던 일."""
        proc = self.run_usage("--codex-home", str(self.home / "none"), "--claude-screen", str(self.home / "none.txt"))
        data = json.loads(proc.stdout)
        self.assertEqual((data["claude"], data["fable"], data["codex"]), (None, None, None))
        self.assertEqual(data["notes"], ["screen-unreadable", "claude-weekly-not-on-screen", "fable-weekly-not-on-screen", "codex-no-sessions"])
        self.assertNotIn(str(self.home), proc.stdout)

    def test_herdr_failure_is_a_fixed_word(self):
        fake = self.home / "bin"
        fake.mkdir()
        (fake / "herdr").write_text("#!/bin/sh\necho 'who: someone at example dot com' >&2\nexit 3\n", "utf-8")
        (fake / "herdr").chmod(0o755)
        proc = subprocess.run([sys.executable, "-I", str(SKILL / "scripts/usage.py"), "--herdr-agent", "x", "--codex-home", str(self.home)],
                              capture_output=True, text=True, encoding="utf-8", timeout=60,
                              env={**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"})
        data = json.loads(proc.stdout)
        self.assertEqual(data["notes"][0], "herdr-read-failed-exit-3")
        self.assertNotIn("someone", proc.stdout)


class RoutingDocs(unittest.TestCase):
    def read(self, name):
        return (SKILL / name).read_text("utf-8")

    def test_skill_routes_before_every_launch(self):
        step3 = self.read("SKILL.md").split("### 3.")[1].split("### 4.")[0]
        for need in ("references/routing.md", "`usage.py`", "`route.py`", "brief의 `model`", "`보낼 곳: 없음`이나 `띄워도 되나: 아니오`면 띄우지 않는다",
                     "감으로 고르지 않는다", "하나씩 띄우고 그때마다 다시 잰다"):
            self.assertIn(need, step3)
        self.assertNotIn("동시에 띄운다", step3)
        self.assertIn("model:", self.read("assets/brief.md"))

    def test_router_args_go_into_the_command_exactly_once(self):
        """astra 리뷰: 예시 명령에도 같은 옵션이 있어 붙이면 두 번 들어가던 일."""
        launch = self.read("references/dispatch.md").split("## 띄우는 방법")[1].split("## 결과를 받으면")[0]
        self.assertIn('--kind claude --pane <pane id> -- -n "<프로젝트> · <하는 일>" --permission-mode auto <route.py가 낸 인자>\n', launch)
        self.assertIn("--kind codex --pane <pane id> -- <route.py가 낸 인자>\n", launch)
        self.assertNotRegex(launch, r"--model|--effort|workspace-write|--add-dir|model_reasoning_effort")
        self.assertNotRegex(launch, "bypassPermissions|dangerously|danger-full-access")
        self.assertIn("`보낼 곳: 없음`이나 `띄워도 되나: 아니오`", launch)

    def test_move_check_comes_before_the_old_result_is_renamed(self):
        resume = self.read("references/dispatch.md").split("## 이어 시키기")[1].split("## 치우기")[0]
        self.assertLess(resume.index("routing.md#도는-작업자-옮기기"), resume.index("result-1.md"))

    def test_only_the_user_spends_a_reset(self):
        doc = self.read("references/routing.md").split("## 리셋권")[1].split("## ")[0]
        for need in ("**사용자만 쓴다.**", "되돌릴 수 없다", "터미널에는 없다", "decisions.md", "묻지 않고 기다리거나", "독립 리뷰(`--other-eyes`)에는 묻지 않는다"):
            self.assertIn(need, doc)
        self.assertIn("**리셋권은 사용자만 쓴다.**", self.read("SKILL.md"))

    def test_moving_a_worker_has_conditions(self):
        doc = self.read("references/routing.md").split("## 도는 작업자 옮기기")[1]
        for need in ("일하는 도중에는 옮기지 않는다", "라운드 사이", "실행 시작", "--resume", "옛 세션을 닫는 것은 사용자에게 묻는다",
                     "사용자가 직접 쓰는 세션은 건드리지 않는다"):
            self.assertIn(need, doc)

    def test_codex_worker_rules(self):
        doc = self.read("references/routing.md").split("## Codex 작업자")[1].split("## ")[0]
        for need in ("`-C <상태>/tasks/<id>/out`", "`--add-dir <상태>/tasks/<id>/out`", "`--approve-for-me`", "`-a on-request`",
                     "끄는 옵션은 쓰지 않는다", "대신 누르지 않고", "brief는 쓰지 못한다", "`--kind run`으로 인자를 받아"):
            self.assertIn(need, doc)
        launch = self.read("references/dispatch.md").split("## 띄우는 방법")[1].split("## 결과를 받으면")[0]
        for need in ("`<상태>/tasks/<id>/out/result.md`", "mkdir -p <상태>/tasks/<id>/out", "`codex <route.py가 낸 인자>`"):
            self.assertIn(need, launch)   # astra 리뷰: 손으로 띄울 때 권한 인자가 빠지던 일
        self.assertNotIn("codex-review", self.read("references/routing.md"))  # 비서실장이 리뷰 도구를 직접 부르지 않는다

    def test_eval_fixtures_use_the_fields_usage_py_writes(self):
        """astra 리뷰: fixture가 옛 필드 이름을 써서 값이 무시되던 일."""
        for path in sorted((SKILL / "evals/fixtures/routing").glob("usage-*.json")):
            data = json.loads(path.read_text("utf-8"))
            self.assertLessEqual(set(data), {"cli", "claude", "fable", "codex", "mem_free_pct", "notes"}, path.name)
            self.assertEqual(route.decide("scout", "mid", data, other_eyes=True)["provider"], "codex", path.name)
            self.assertIsNone(route.decide("scout", "mid", {**data, "cli": {"claude": True, "codex": False}}, other_eyes=True)["provider"])

    def test_rules_in_the_doc_say_when_codex_is_usable(self):
        rules = self.read("references/routing.md").split("`route.py`는 위에서부터")[1].split("## ")[0]
        self.assertIn("4. `mid`·`low`인데 Codex를 쓸 수 있고", rules)
        self.assertIn("Codex를 못 쓰면 띄우지 않고 사용자에게 묻는다", rules)
        doc = self.read("references/routing.md")
        self.assertIn('grep -A1 -E "^[[:space:]]*Current week \\(all models\\)[[:space:]]*$" | grep -Eq "[0-9]% used[[:space:]]*$" && herdr agent send-keys', doc)
        check = doc.split("--lines 200 | ")[1].split(" && herdr agent send-keys")[0]   # 예시의 검사를 그대로 돌려 본다
        seen = lambda text: subprocess.run(check, shell=True, input=text, text=True).returncode == 0  # noqa: E731
        self.assertTrue(seen(SCREEN.replace("\x1b[38;2;1;2;3m", "").replace("\x1b[0m", "")))
        self.assertFalse(seen("Current week (all models) 예시에는 12% used가 보입니다\n"))
        self.assertFalse(seen("Current week를 읽는 방법입니다\n"))
        self.assertIn("--task <id> --workspace <작업 공간> --usage", doc)
        for need in ("`--not-model <만든 모델의 별칭>`", "`--workspace <작업 공간>`", "임시 폴더나 그 작업 공간 안", "보고판이 `내 차례`에 올린다"):
            self.assertIn(need, doc)

    def test_thresholds_in_the_doc_match_the_code(self):
        doc = self.read("references/routing.md")
        for text in (f"{route.OUT}% 이상 썼다", f"{route.TIGHT_USED}% 이상 썼다", f"{route.SPARE_AT_RESET}%도 못 쓴다",
                     f"초기화가 {route.NEAR_RESET_H}시간 안", f"초기화가 {route.LONG_RESET_H}시간 넘게", f"빈 메모리 {route.MEM_MIN_FREE}% 미만",
                     f"적어도 {route.MIN_ELAPSED_H}시간", f"{route.STALE_H}시간 넘게 묵은 값", f"{route.SNAPSHOT_MAX_MIN}분 넘게 지난"):
            self.assertIn(text, doc)

    def test_no_model_versions_in_the_skill(self):
        """모델 판 이름은 낡는다. 별칭과 설정의 기본 모델만 쓴다."""
        for path in SKILL.rglob("*"):
            if path.suffix in (".md", ".py", ".yaml", ".json"):
                self.assertIsNone(re.search(r"claude-[a-z]+-\d|gpt-\d|\b(?:fable|opus|sonnet|haiku) \d", path.read_text("utf-8"), re.I), path.name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
