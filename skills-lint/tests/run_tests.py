#!/usr/bin/env python3
"""skills_lint.py 테스트. 임시 폴더에 만든 가짜 스킬만 쓴다(네트워크 없음, 실제 홈 폴더를 읽지 않음).

사용: python3 -I tests/run_tests.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "skills_lint.py")


def front(name, desc="하는 일과 쓰는 때.", extra=""):
    return f"---\nname: {name}\ndescription: {desc}\n{extra}---\n"


class LintTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="skills-lint-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp = os.path.realpath(tmp.name)
        self.home, self.repo = self.p("home"), self.p("repo")
        os.makedirs(self.home)
        os.makedirs(self.repo)

    def p(self, *names):
        return os.path.join(self.tmp, *names)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def skill(self, folder, text, base=None):
        self.write(os.path.join(base or self.repo, folder, "SKILL.md"), text)

    def call(self, *args):
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, cwd=self.home,
                              env=dict(os.environ, HOME=self.home))

    def lint(self, *args):
        r = self.call(*(args or ("--root", self.repo)), "--json", "--fail-on", "never")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def codes(self, *args):
        return sorted(i["code"] for i in self.lint(*args)["issues"])

    def one(self, text, folder="alpha"):
        """스킬 하나만 있는 저장소의 문제 코드."""
        self.skill(folder, text)
        return self.codes()

    # 깨끗한 스킬
    def test_clean_skill(self):
        self.assertEqual(self.one(front("alpha", '"하는 일: 쓰는 때"', "license: MIT\nmetadata:\n  version: \"1.0\"\n") + "본문\n"), [])

    # 머리말
    def test_frontmatter_missing_and_unclosed(self):
        self.assertEqual(self.one("# 제목\n"), ["frontmatter-missing"])
        self.assertEqual(self.one("---\nname: alpha\ndescription: x\n# 본문\n"), ["frontmatter-unclosed"])

    def test_broken_yaml_shapes(self):
        bad = {"콜론": "고침: 이것", "줄 끝 콜론": "목록:", "이어진 줄의 콜론": "하나\n  둘: 셋", "안쪽 큰따옴표": '"a "b" c"',
               "안쪽 작은따옴표": "'it's'", "닫지 않음": '"열림', "대괄호": "[old] x", "골뱅이": "@x", "별표": "*x", "목록": "- a"}
        for why, desc in bad.items():
            self.assertEqual(self.one(front("alpha", desc)), ["frontmatter-yaml"], why)

    def test_valid_yaml_shapes(self):
        good = {"따옴표": '"a: b"', "작은따옴표": "'it''s: ok'", "주석": "글 # 참고: 주석", "주소": "https://example.com 을 봄",
                "접은 글": ">-\n  a: b\n  c", "여러 줄": "하나\n  둘", "여러 줄 따옴표": '"하나\n  둘: 셋"'}
        for why, desc in good.items():
            self.assertEqual(self.one(front("alpha", desc)), [], why)

    def test_line_that_is_not_a_field_and_tab(self):
        self.assertEqual(self.one("---\nname: alpha\ndescription: x\n그냥 글\n---\n"), ["frontmatter-yaml"])
        self.assertEqual(self.one("---\nname: alpha\ndescription: x\nmetadata:\n\tversion: y\n---\n"), ["frontmatter-yaml"])

    def test_bom_and_crlf_are_read(self):
        self.assertEqual(self.one("﻿" + front("alpha").replace("\n", "\r\n")), [])

    # 규격
    def test_name_rules(self):
        for name in ("Alpha", "al_pha", "-alpha", "al--pha", "a" * 65):
            self.assertEqual(self.one(front(name), folder=name), ["name-format"], name)
            os.rename(self.repo, self.p("done-" + str(len(os.listdir(self.tmp)))))
        self.assertEqual(self.one(front("a" * 64), folder="a" * 64), [])

    def test_name_must_match_folder(self):
        self.assertEqual(self.one(front("beta")), ["name-folder"])

    def test_required_fields(self):
        self.assertEqual(self.one("---\nlicense: MIT\n---\n"), ["description-missing", "name-missing"])

    def test_description_length_boundary(self):
        self.assertEqual(self.one(front("alpha", "가" * 1024)), [])
        self.assertEqual(self.one(front("alpha", "가" * 1025)), ["description-length"])

    def test_compatibility_length(self):
        self.assertEqual(self.one(front("alpha", extra="compatibility: " + "x" * 501 + "\n")), ["compatibility-length"])

    def test_fields_outside_the_spec(self):
        issues = self.one(front("alpha", extra="allowed-tools: Read\nargument-hint: \"[x]\"\nhooks:\n  Stop: x\n"))
        self.assertEqual(issues, ["field-unknown", "field-unknown"])

    # 설명 길이
    def test_description_cost_skips_manual_skills(self):
        self.skill("alpha", front("alpha", "12345", "when_to_use: 678\n"))
        self.skill("beta", front("beta", "x" * 100, "disable-model-invocation: true\n"))
        r = self.lint()
        self.assertEqual((r["skills"], r["invocable"], r["desc_chars_invocable"]), (2, 1, 8))
        self.assertEqual(r["longest"], [dict(name="alpha", desc_chars=8)])

    def test_scripts_without_tests(self):
        self.skill("alpha", front("alpha"))
        self.write(os.path.join(self.repo, "alpha", "scripts", "a.py"), "")
        self.assertEqual(self.lint()["scripts_without_tests"], ["alpha"])
        self.write(os.path.join(self.repo, "alpha", "tests", "t.py"), "")
        self.assertEqual(self.lint()["scripts_without_tests"], [])

    # 이름·트리거 겹침
    def test_duplicate_name_is_error_in_repo(self):
        self.skill("alpha", front("alpha"))
        self.skill("pack/alpha", front("alpha"))
        r = self.lint()
        self.assertEqual([(i["code"], i["level"]) for i in r["issues"]], [("name-duplicate", "error")])
        self.assertIn("내용 같음", r["issues"][0]["message"])

    def test_trigger_overlap_uses_quoted_phrases_only(self):
        self.skill("alpha", front("alpha", "\"슬라이드를 만든다. '슬라이드 생성', 'make deck'에 쓴다.\""))
        self.skill("beta", front("beta", "\"발표 자료. '슬라이드  생성', “Make Deck”을 말할 때. user's own words, it's fine.\""))
        self.skill("gamma", front("gamma", "슬라이드 생성 같은 말을 따옴표 없이 씀."))
        self.skill("delta", front("delta", "\"'make deck'\"", "disable-model-invocation: true\n"))
        self.assertEqual(self.lint()["trigger_overlaps"], [dict(phrase="make deck", skills=["alpha", "beta"]),
                                                           dict(phrase="슬라이드 생성", skills=["alpha", "beta"])])

    # 링크와 경로
    def test_broken_links(self):
        self.write(os.path.join(self.repo, "alpha", "references", "a b.md"), "[위](../SKILL.md) [뿌리](references/a%20b.md) [없음](x.md)\n")
        self.skill("alpha", front("alpha") + "\n".join([
            "[됨](references/a%20b.md#절) [웹](https://example.com/x.md) [위치](#절) [예시](url) [자리](<이름>.md) ![](img/none.png)",
            "```", "[코드](none.md)", "```", "`[코드](none.md)` <!-- [주석](none.md) -->", "[정의]: references/none.md"]))
        got = sorted((i["code"], i["level"], i["message"].split(": ")[1], i["line"]) for i in self.lint()["issues"])
        self.assertEqual(got, [("broken-link", "error", "img/none.png", 5), ("broken-link", "error", "references/none.md", 10),
                               ("broken-link", "error", "x.md", 1)])

    def test_stale_paths_inside_the_skill(self):
        self.write(os.path.join(self.repo, "alpha", "scripts", "ok.py"), "")
        self.write(os.path.join(self.repo, "beta", "references", "shared.md"), "")
        self.skill("beta", front("beta"))
        self.skill("alpha", front("alpha") + "\n".join([
            "`scripts/ok.py` `scripts/gone.py` python3 <skill>/scripts/gone2.py ${CLAUDE_SKILL_DIR}/scripts/ok.py",
            "/beta의 `references/shared.md`, 내 저장소의 app/scripts/x.py, scripts/*.py, scripts/<이름>.py, assets/out.png",
            "다시 scripts/gone.py"]))
        self.assertEqual([(i["code"], i["message"].split(": ")[1], i["line"]) for i in self.lint()["issues"]],
                         [("stale-path", "scripts/gone.py", 5), ("stale-path", "scripts/gone2.py", 5)])

    def test_install_paths_to_known_skills(self):
        self.write(os.path.join(self.repo, "alpha", "scripts", "ok.py"), "")
        self.skill("alpha", front("alpha") + "~/.claude/skills/alpha/scripts/ok.py\n~/.claude/skills/alpha/scripts/gone.py\n"
                   "~/.claude/skills/other/x.py\n~/.claude/skills/<이름>/x.py\n")
        self.assertEqual([(i["code"], i["line"]) for i in self.lint()["issues"]], [("stale-path", 6)])

    def test_absolute_home_paths_in_repo(self):
        self.skill("alpha", front("alpha") + "/Users/" + "someone/work\n/home/user/work\nhttps://example.com/home/someone\n")
        self.assertEqual([(i["code"], i["line"]) for i in self.lint()["issues"]], [("abs-path", 5)])

    # 설치된 폴더
    def test_installed_roots_symlinks_and_levels(self):
        self.skill("alpha", front("alpha"), self.p("src"))
        for d in (".claude", ".agents"):
            os.makedirs(os.path.join(self.home, d, "skills"))
            os.symlink(self.p("src", "alpha"), os.path.join(self.home, d, "skills", "alpha"))
        os.symlink(self.p("gone"), os.path.join(self.home, ".claude", "skills", "old"))
        self.skill("beta", front("beta", "하나"), os.path.join(self.home, ".claude", "skills"))
        self.skill("beta", front("beta", "둘"), os.path.join(self.home, ".agents", "skills"))
        self.skill("deep/nested", front("nested"), os.path.join(self.home, ".claude", "skills"))
        r = self.lint("--fail-on", "never")
        self.assertEqual((r["mode"], r["skills"]), ("installed", 3))
        self.assertEqual([(i["code"], i["level"]) for i in r["issues"]], [("dangling-symlink", "error"), ("name-duplicate", "warning")])
        self.assertIn("내용 다름", r["issues"][1]["message"])
        self.assertEqual([(x["path"], x["skills"]) for x in r["roots"]], [(".claude/skills", 2), (".agents/skills", 2)])

    def test_installed_stale_paths(self):
        base = os.path.join(self.home, ".claude", "skills")
        self.write(self.p("here", "x.txt"), "")
        self.skill("alpha", front("alpha") + "~/.claude/skills/removed/run.py\n/Users/" + "someone/none/x.py\n~/.cache/made-later\n", base)
        self.assertEqual([(i["code"], i["line"]) for i in self.lint("--fail-on", "never")["issues"]], [("stale-path", 5), ("stale-path", 6)])

    # 저장소 찾기
    def test_repo_search(self):
        for path in ("a", "skills/b", "skills/pack/c", ".claude/skills/d", "plugins/p/skills/e"):
            self.skill(path, front(os.path.basename(path)))
        for path in ("a/inner", "a/tests/fixtures/x", "tests/y", "node_modules/z", ".hidden/w"):
            self.skill(path, "깨짐")
        os.symlink(os.path.join(self.repo, "a"), os.path.join(self.repo, "link"))
        r = self.lint()
        self.assertEqual([s["name"] for s in r["items"]], ["a", "b", "c", "d", "e"])
        self.assertEqual(r["issues"], [])

    def test_root_that_is_one_skill(self):
        self.skill("alpha", front("alpha"))
        self.assertEqual(self.lint("--root", os.path.join(self.repo, "alpha"))["skills"], 1)

    # 종료 코드와 부작용
    def test_exit_codes(self):
        self.skill("alpha", front("alpha", extra="argument-hint: x\n"))
        root = ("--root", self.repo)
        self.assertEqual(self.call(*root).returncode, 0)
        self.assertEqual(self.call(*root, "--fail-on", "warning").returncode, 1)
        self.skill("beta", front("other"))
        self.assertEqual(self.call(*root).returncode, 1)
        self.assertEqual(self.call(*root, "--fail-on", "never").returncode, 0)
        self.assertEqual(self.call("--root", self.p("none")).returncode, 2)
        os.makedirs(self.p("empty"))
        self.assertEqual(self.call("--root", self.p("empty")).returncode, 2)
        self.assertEqual(self.call().returncode, 2)

    def test_does_not_change_files_and_hides_home(self):
        base = os.path.join(self.home, ".claude", "skills")
        self.skill("alpha", front("beta") + "[x](none.md)\n", base)
        path = os.path.join(base, "alpha", "SKILL.md")
        before = (os.stat(path).st_mtime_ns, sorted(os.listdir(os.path.dirname(path))))
        out = self.call("--fail-on", "never")
        self.assertEqual((os.stat(path).st_mtime_ns, sorted(os.listdir(os.path.dirname(path)))), before)
        self.assertIn("broken-link", out.stdout)
        self.assertNotIn(self.home, out.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
