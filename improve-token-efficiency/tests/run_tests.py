#!/usr/bin/env python3
"""가짜 세션 기록만 쓰는 테스트. 네트워크·실제 기록을 쓰지 않는다.

  python3 -I tests/run_tests.py
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 11, 24)
SECRET = "비밀-프롬프트-본문-7391"
SECRET_FILE = "/work/acme-web/secret-plan.md"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.dont_write_bytecode = True
A = load("analyze_sessions")
B = load("build_dashboard")
PRICING = A.load_pricing()


def line(mid="m1", req="r1", model="claude-opus-5-5", inp=0, out=0, w5=0, w1=0, cr=0, content=(), ts="2026-11-01T00:00:00Z", **usage):
    rec = {"type": "assistant", "timestamp": ts, "message": {"model": model, "content": list(content), "usage": {
        "input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr, "cache_creation_input_tokens": w5 + w1,
        "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}, **usage}}}
    if mid:
        rec["message"]["id"] = mid
    if req:
        rec["requestId"] = req
    return rec


def at(cwd, rec):
    return {**rec, "cwd": str(cwd)}


def user(text):
    return {"type": "user", "timestamp": "2026-11-01T00:00:00Z", "message": {"role": "user", "content": text}}


def tool(tid, name="Bash", **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.logs = self.tmp / "logs"
        self.logs.mkdir()

    def write(self, name, *records, folder=None):
        path = (folder or self.logs) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)) + "\n" for r in records), encoding="utf-8")

    def run_analysis(self, pricing=PRICING, today=TODAY):
        return A.analyze(A.session_files(self.logs), pricing, "demo-api", today)

    def cost(self, *records, **kw):
        self.write("s1.jsonl", *records)
        return self.run_analysis(**kw)["totals"]["cost_usd"]

    def cli(self, script, *args, home=None, cwd=None):
        env = {"HOME": str(home or self.tmp), "PATH": os.environ["PATH"], "LC_ALL": "en_US.UTF-8"}
        return subprocess.run([sys.executable, "-I", str(SKILL / "scripts" / script), *map(str, args)],
                              capture_output=True, text=True, env=env, cwd=cwd or self.tmp)


class Pricing(Case):
    MILLION = dict(inp=1_000_000, out=1_000_000)

    def test_재현_opus_4_7은_5와_25달러(self):
        self.assertAlmostEqual(self.cost(line(model="claude-opus-4-7", **self.MILLION)), 30)

    def test_재현_haiku_4_5는_1과_5달러(self):
        self.assertAlmostEqual(self.cost(line(model="claude-haiku-4-5-20251001", **self.MILLION)), 6)

    def test_재현_새_모델을_옛_가격으로_세지_않는다(self):
        self.assertAlmostEqual(self.cost(line(**self.MILLION, cr=1_000_000)), 4 + 20 + 0.2)

    def test_캐시_쓰기_5분과_1시간을_따로_센다(self):
        self.write("s1.jsonl", line(w5=1_000_000, w1=1_000_000))
        t = self.run_analysis()["totals"]
        self.assertAlmostEqual(t["cost_usd"], 5 + 8)
        self.assertAlmostEqual(t["premium_1h_usd"], 3)

    def test_긴_프롬프트_가격은_요청마다_따로(self):
        short = line("a", "a", "claude-haiku-5-5", inp=100_000, out=1_000_000)
        long = line("b", "b", "claude-haiku-5-5", inp=1, cr=100_000, out=1_000_000)
        self.assertAlmostEqual(self.cost(short), 0.01 + 0.5)
        self.assertAlmostEqual(self.cost(long), 1 * 0.5 / 1e6 + 100_000 * 0.05 / 1e6 + 2.5)

    def test_fast와_us_배율(self):
        self.assertAlmostEqual(self.cost(line(**self.MILLION, speed="fast")), 48)
        self.assertAlmostEqual(self.cost(line(**self.MILLION, inference_geo="us")), 26.4)
        self.assertAlmostEqual(self.cost(line(**self.MILLION, speed="standard", inference_geo="not_available")), 24)

    def test_fast_가격이_없는_모델은_가격_모름(self):
        self.assertIsNone(self.cost(line(model="claude-sonnet-5-5", inp=10, speed="fast")))

    def test_재현_모르는_모델은_금액을_만들지_않는다(self):
        for model in ("some-new-model", "global.anthropic.claude-opus-4-8", "claude-opus-5-5-fast", "claude-mythos-preview"):
            self.assertIsNone(self.cost(line(model=model, inp=10)), model)

    def test_일부만_모르면_나머지만_더하고_몇_건인지_적는다(self):
        self.write("s1.jsonl", line("a", "a", inp=1_000_000), line("b", "b", "some-new-model", inp=500, out=7))
        t = self.run_analysis()["totals"]
        self.assertAlmostEqual(t["cost_usd"], 4)
        self.assertEqual((t["unpriced_responses"], t["unpriced_tokens"], t["input"]), (1, 507, 1_000_500))

    def test_null_가격은_가격_모름(self):
        for rates in (None, {**PRICING["models"]["claude-opus-5-5"], "cache_read": None}):
            self.assertIsNone(self.cost(line(inp=10), pricing={**PRICING, "models": {"claude-opus-5-5": rates}}))

    def test_synthetic_줄은_응답이_아니다(self):
        self.write("s1.jsonl", line("a", "a", inp=10), line("b", None, "<synthetic>", inp=10))
        self.assertEqual(self.run_analysis()["totals"]["responses"], 1)

    def test_가격표_90일_초과면_경고(self):
        self.write("s1.jsonl", line(inp=10))
        checked = datetime.date.fromisoformat(PRICING["checked_on"])
        for days, stale in ((90, False), (91, True)):
            data = self.run_analysis(today=checked + datetime.timedelta(days=days))
            self.assertIs(data["pricing"]["stale"], stale)
            self.assertIs("가격표를 확인한 지" in B.build_html(data), stale)

    def test_가격표_모양(self):
        self.assertTrue(PRICING["source_url"].startswith("https://platform.claude.com/"))
        for model, rates in PRICING["models"].items():
            if rates:
                self.assertTrue(all(isinstance(rates[k], (int, float)) for k in A.KINDS), model)
                self.assertAlmostEqual(rates["cache_write_5m"], rates["input"] * 1.25, msg=model)
                self.assertAlmostEqual(rates["cache_write_1h"], rates["input"] * 2, msg=model)

    def test_TTL_구분이_없으면_5분으로_세고_적는다(self):
        rec = line(w5=1_000_000)
        del rec["message"]["usage"]["cache_creation"]
        self.write("s1.jsonl", rec)
        data = self.run_analysis()
        self.assertAlmostEqual(data["totals"]["cost_usd"], 5)
        self.assertEqual(data["notes"]["cache_write_ttl_unknown_tokens"], 1_000_000)


class FindDir(Case):
    def test_재현_영숫자가_아닌_글자는_모두_하이픈(self):
        self.assertEqual(A.encode_path("/work/my_app.v2 한글-x"), "-work-my-app-v2----x")

    def test_밑줄_점_한글_프로젝트를_찾는다(self):
        for name in ("my_app", "site.io", "한글프로젝트", unicodedata.normalize("NFD", "한글엔에프디")):
            repo = self.tmp / name
            repo.mkdir()
            folder = self.tmp / ".claude/projects" / re.sub(r"[^a-zA-Z0-9]", "-", unicodedata.normalize("NFC", str(repo)))
            self.write("s1.jsonl", at(repo, line(inp=10)), folder=folder)
            r = self.cli("analyze_sessions.py", "--repo", repo, "--out-dir", self.tmp / f"out-{len(name)}-{name.isascii()}")
            self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")

    def test_심볼릭_링크는_실제_경로로_찾는다(self):
        real, root = self.tmp / "real", self.tmp / "p"
        real.mkdir()
        (self.tmp / "link").symlink_to(real)
        (root / A.encode_path(str(real))).mkdir(parents=True)
        self.assertEqual(A.find_sessions_dir(str(self.tmp / "link"), root), root / A.encode_path(str(real)))

    def test_긴_경로는_앞_200자로_찾고_여럿이면_멈춘다(self):
        repo, root = "/" + "a" * 250, self.tmp / "p"
        (root / (A.encode_path(repo)[:200] + "-x1")).mkdir(parents=True)
        self.assertTrue(A.find_sessions_dir(repo, root).name.endswith("-x1"))
        (root / (A.encode_path(repo)[:200] + "-x2")).mkdir()
        with self.assertRaises(SystemExit):
            A.find_sessions_dir(repo, root)

    def test_기록이_없으면_2로_끝난다(self):
        self.assertEqual(self.cli("analyze_sessions.py", "--repo", self.tmp).returncode, 2)
        self.assertFalse((self.tmp / "token-report").exists())


class SameFolderName(Case):
    """my_app과 my-app은 기록 폴더 이름이 같다. 기록에 적힌 cwd로 가른다."""

    def setUp(self):
        super().setUp()
        self.ours, self.other = self.tmp / "my_app", self.tmp / "my-app"
        for d in (self.ours, self.other):
            d.mkdir()
        self.folder = self.tmp / ".claude/projects" / A.encode_path(str(self.ours))

    def analyze(self, repo=None):
        r = self.cli("analyze_sessions.py", "--repo", repo or self.ours, "--out-dir", self.tmp / "out")
        out = self.tmp / "out/token-analysis.json"
        return r, json.loads(out.read_text()) if r.returncode == 0 else None

    def test_재현_다른_프로젝트의_토큰과_세션이_섞이지_않는다(self):
        self.write("aaaa.jsonl", at(self.ours, line("a", "a", inp=10)), folder=self.folder)
        self.write("bbbb.jsonl", at(self.other, line("b", "b", inp=90, content=[tool("t1")])), folder=self.folder)
        r, data = self.analyze()
        self.assertEqual((data["totals"]["input"], data["totals"]["tool_calls"]), (10, 0))
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["aaaa"])
        self.assertEqual((data["notes"]["other_project_responses"], data["notes"]["other_project_tokens"]), (1, 90))
        self.assertIn("다른 프로젝트", r.stderr)
        self.assertIn("다른 프로젝트", B.build_html(data))
        self.assertNotIn("bbbb", json.dumps(data))
        _, data = self.analyze(self.other)
        self.assertEqual((data["totals"]["input"], data["notes"]["other_project_responses"]), (90, 1))

    def test_귀속을_모르는_기록은_합계에서_빼고_건수를_적는다(self):
        self.write("aaaa.jsonl", at(self.ours, line("a", "a", inp=10)), folder=self.folder)
        self.write("cccc.jsonl", line("c", "c", inp=5), line("c", "c", inp=5), at("/elsewhere", line("d", "d", inp=2)), folder=self.folder)
        r, data = self.analyze()
        n = data["notes"]
        self.assertEqual((data["totals"]["input"], n["unclear_project_responses"], n["unclear_project_tokens"]), (10, 2, 7))
        self.assertIn("2건", r.stderr)
        self.assertIn("어느 프로젝트", B.build_html(data))

    def test_하위_폴더와_옮겨_간_cwd는_앞의_귀속을_따른다(self):
        self.write("aaaa.jsonl", at(self.ours, user("x")), at(self.ours / "sub", line("a", "a", inp=1)),
                   at("/elsewhere", line("b", "b", inp=2)), line("c", "c", inp=4), folder=self.folder)
        self.write("aaaa/subagents/agent-x.jsonl", at("/elsewhere", line("d", "d", inp=8)), folder=self.folder)
        _, data = self.analyze()
        self.assertEqual((data["totals"]["input"], data["notes"]["unclear_project_responses"]), (15, 0))

    def test_한_파일에서_다른_프로젝트로_이어_쓴_부분만_뺀다(self):
        self.write("aaaa.jsonl", at(self.ours, line("a", "a", inp=1)), at(self.other / "sub", line("b", "b", inp=90)),
                   line("c", "c", inp=90), folder=self.folder)
        _, data = self.analyze()
        self.assertEqual((data["totals"]["input"], data["notes"]["other_project_responses"]), (1, 2))

    def test_하위_에이전트의_귀속은_형제에게_넘어가지_않는다(self):
        self.write("aaaa/subagents/agent-1.jsonl", at(self.ours, line("a", "a", inp=10)), folder=self.folder)
        self.write("aaaa/subagents/agent-2.jsonl", line("b", "b", inp=90), folder=self.folder)
        _, data = self.analyze()
        self.assertEqual((data["totals"]["input"], data["notes"]["unclear_project_tokens"]), (10, 90))

    def test_부모의_귀속이_둘이면_하위_에이전트가_물려받지_않는다(self):
        self.write("aaaa.jsonl", at(self.ours, line("a", "a", inp=1)), at(self.other, line("b", "b", inp=2)), folder=self.folder)
        self.write("aaaa/subagents/agent-1.jsonl", line("c", "c", inp=4), folder=self.folder)
        _, data = self.analyze()
        n = data["notes"]
        self.assertEqual((data["totals"]["input"], n["other_project_tokens"], n["unclear_project_tokens"]), (1, 2, 4))

    def test_심볼릭_링크로_적힌_cwd도_같은_프로젝트다(self):
        link = self.tmp / "link"
        link.symlink_to(self.ours)
        self.write("aaaa.jsonl", at(link, line("a", "a", inp=1)), folder=self.folder)
        for repo in (self.ours, link):
            self.assertEqual(self.analyze(repo)[1]["totals"]["input"], 1)

    def test_남의_기록만_있으면_2로_끝나고_건수를_말한다(self):
        self.write("bbbb.jsonl", at(self.other, line("b", "b", inp=90)), folder=self.folder)
        r, _ = self.analyze()
        self.assertEqual(r.returncode, 2)
        self.assertIn("다른 프로젝트", r.stderr)

    def test_폴더를_직접_골라도_repo를_적으면_가른다(self):
        self.write("aaaa.jsonl", at(self.ours, line("a", "a", inp=10)), folder=self.logs)
        self.write("bbbb.jsonl", at(self.other, line("b", "b", inp=90)), folder=self.logs)
        out = self.tmp / "out"
        r = self.cli("analyze_sessions.py", "--repo", self.ours, "--sessions-dir", self.logs, "--out-dir", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((out / "token-analysis.json").read_text())
        self.assertEqual((data["totals"]["input"], data["label"]), (10, "my_app"))
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["aaaa"])
        self.assertEqual(data["notes"]["other_project_tokens"], 90)

    def test_폴더를_직접_고르면_가르지_않는다(self):
        self.write("bbbb.jsonl", at(self.other, line("b", "b", inp=90)), folder=self.folder)
        r = self.cli("analyze_sessions.py", "--sessions-dir", self.folder, "--out-dir", self.tmp / "out")
        self.assertEqual(r.returncode, 0, r.stderr)


class Dedup(Case):
    def test_재현_한_응답이_여러_줄이면_한_번만(self):
        self.write("s1.jsonl",
                   line(inp=100, out=1, content=[{"type": "text", "text": "a"}]),
                   line(inp=100, out=50, content=[tool("t1")]),
                   line(inp=100, out=50, content=[tool("t2"), tool("t2")]))
        data = self.run_analysis()
        t = data["totals"]
        self.assertEqual((t["responses"], t["input"], t["output"]), (1, 100, 50))
        self.assertEqual(data["notes"]["duplicate_lines"], 2)
        self.assertEqual(t["tool_calls"], 2)  # 뒤 줄에 있는 도구 호출은 잃지 않는다

    def test_출력이_적힌_줄이_먼저_와도_큰_값을_남긴다(self):
        self.write("s1.jsonl", line(out=50), line(out=1))
        self.assertEqual(self.run_analysis()["totals"]["output"], 50)

    def test_다른_세션에_복사된_응답도_한_번만(self):
        same = line(inp=100, content=[tool("t1")])
        self.write("s1.jsonl", same)
        self.write("s2.jsonl", same, line("m2", "r2", inp=7))
        t = self.run_analysis()["totals"]
        self.assertEqual((t["responses"], t["input"], t["tool_calls"]), (2, 107, 1))

    def test_요청이_다르면_따로_id가_없으면_줄마다(self):
        self.write("s1.jsonl", line(req="r1", inp=1), line(req="r2", inp=1), line(None, None, inp=1), line(None, None, inp=1))
        data = self.run_analysis()
        self.assertEqual((data["totals"]["responses"], data["notes"]["lines_without_id"]), (4, 2))

    def test_하위_에이전트_기록은_부모_세션에(self):
        self.write("s1.jsonl", line(inp=10))
        self.write("s1/subagents/agent-a.jsonl", line("m2", "r2", inp=5))
        self.write("s1/subagents/workflows/w1/agent-b.jsonl", line("m3", "r3", inp=3))
        data = self.run_analysis()
        self.assertEqual((data["totals"]["input"], len(data["sessions"])), (18, 1))

    def test_깨진_줄과_이상한_값을_견딘다(self):
        self.write("s1.jsonl", "{깨짐", "[]", "3", json.dumps({"type": "assistant", "message": None}),
                   json.dumps({"type": "assistant", "message": {"id": "x", "usage": None}}),
                   line("y", "y", inp=True, out=-5, cr="9"), line("z", "z", inp=10, content=["글", None, {"type": "tool_use"}]))
        data = self.run_analysis()
        self.assertEqual((data["notes"]["broken_lines"], data["totals"]["input"], data["totals"]["responses"]), (1, 10, 1))


class Output(Case):
    def build(self, *extra):
        self.write("s1.jsonl", user(SECRET), line(inp=1000, out=200, cr=5000, w1=100, content=[
            {"type": "text", "text": SECRET}, tool("t1", "Read", file_path=SECRET_FILE), tool("t2", "Read", file_path=SECRET_FILE),
            tool("t3", "Bash", command=SECRET)]))
        r = self.cli("analyze_sessions.py", "--sessions-dir", self.logs, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.tmp / "token-report"
        r2 = self.cli("build_dashboard.py", "--out-dir", out)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        return out, r.stdout + r.stderr + r2.stdout

    def test_재현_기본_결과는_작업_폴더_token_report에_0600(self):
        out, _ = self.build()
        self.assertEqual(sorted(p.name for p in out.iterdir()), [".gitignore", "token-analysis.json", "token-report.html"])
        self.assertEqual((out / ".gitignore").read_text(), "*\n")
        self.assertEqual(stat.S_IMODE(out.stat().st_mode) & 0o077, 0)
        for name in ("token-analysis.json", "token-report.html"):
            self.assertEqual(stat.S_IMODE((out / name).stat().st_mode), 0o600)

    def test_느슨한_권한의_옛_파일도_0600으로(self):
        out = self.tmp / "token-report"
        out.mkdir()
        (out / "token-analysis.json").write_text("옛것")
        (out / "token-analysis.json").chmod(0o644)
        self.build()
        self.assertEqual(stat.S_IMODE((out / "token-analysis.json").stat().st_mode), 0o600)
        self.assertFalse((out / ".gitignore").exists())  # 이미 있던 폴더는 건드리지 않는다

    def test_심볼릭_링크에는_쓰지_않는다(self):
        target = self.tmp / "other.txt"
        target.write_text("그대로")
        (self.tmp / "link.json").symlink_to(target)
        with self.assertRaises(OSError):
            A.write_private(self.tmp / "link.json", "x")
        self.assertEqual(target.read_text(), "그대로")

    def test_대화_내용과_경로가_결과에_없다(self):
        out, console = self.build()
        for text in ((out / "token-analysis.json").read_text(), (out / "token-report.html").read_text(), console):
            for secret in (SECRET, SECRET_FILE, "secret-plan", str(self.logs)):
                self.assertNotIn(secret, text)

    def test_HTML은_외부_요청이_없다(self):
        html = B.build_html(self.run_after_write())
        self.assertIn("default-src 'none'", html)
        for bad in ("<script", "<link", "<img", "<iframe", "src=", "href=", "url(", "@import", "chart.js"):
            self.assertNotIn(bad, html.lower())

    def test_HTML_이스케이프(self):
        data = self.run_after_write(line("z", "z", "<script>alert(1)</script>", inp=10))
        data["label"] = "<img src=x>"
        html = B.build_html(data)
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)

    def test_모르는_모델만_있으면_달러를_쓰지_않는다(self):
        self.write("s1.jsonl", line(model="some-new-model", inp=1000, out=10, w1=50))
        html = B.build_html(self.run_analysis())
        self.assertIn("가격 모름", html)
        self.assertIn("1건", html)
        self.assertNotRegex(html, r"\$\d")

    def test_같은_기록은_같은_결과(self):
        self.assertEqual(self.run_after_write(), self.run_analysis())

    def run_after_write(self, *more):
        self.write("s1.jsonl", line("a", "a", inp=1000, out=200, cr=9000), *more)
        self.write("s2.jsonl", line("b", "b", "claude-sonnet-5-5", inp=10, out=20))
        return self.run_analysis()


class Files(unittest.TestCase):
    """공개 문서와 스크립트 자체 점검."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    readme = (SKILL / "README.md").read_text(encoding="utf-8")
    scripts = {p: (SKILL / "scripts" / p).read_text(encoding="utf-8") for p in ("analyze_sessions.py", "build_dashboard.py")}

    def test_가격은_한_파일에만(self):
        for name, text in {**self.scripts, "SKILL.md": self.skill, "README.md": self.readme}.items():
            self.assertNotRegex(text, r"claude-(opus|sonnet|haiku|fable)-\d", name)
            self.assertNotRegex(text, r"OPUS_|SONNET_RATIO|PRICING\s*=\s*\{", name)

    def test_재현_없는_옵션과_틀린_조언이_없다(self):
        for name, text in {**self.scripts, "SKILL.md": self.skill, "README.md": self.readme}.items():
            for bad in ("--inline-chartjs", "--weights", "ANTHROPIC_CACHE_TTL", "/tmp", "`/fast`", "<code>/fast</code>", "cdn."):
                self.assertNotIn(bad, text, f"{name}: {bad}")

    def test_문서에_적은_옵션은_코드에_있다(self):
        code = "".join(self.scripts.values())
        for text in (self.skill, self.readme):
            for flag in set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", text)) - {"--skill"}:
                self.assertIn(f'"{flag}"', code, flag)

    def test_SKILL_규격(self):
        head = self.skill.split("---")[1]
        fields = dict(re.findall(r"^(\w+): (.+)$", head, re.M))
        self.assertEqual(fields["name"], SKILL.name)
        self.assertLessEqual(len(fields["description"]), 350)
        self.assertLessEqual(len(self.skill.splitlines()), 100)
        for part in ("## 언제 쓰나", "## 순서", "## 근거", "## 하지 말 것", "## 답 형식"):
            self.assertIn(part, self.skill)

    def test_개인_경로가_없다(self):
        for path in [SKILL / "SKILL.md", SKILL / "README.md", SKILL / "references/pricing.json", *(SKILL / "scripts" / p for p in self.scripts)]:
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"/(Users|home)/\w")


if __name__ == "__main__":
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
