#!/usr/bin/env python3
"""표준 라이브러리 unittest. 네트워크 없음, 임시 폴더만 쓴다.   python3 -I tests/run_tests.py"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORE = ROOT / "scripts" / "score.py"
FILL = ROOT / "scripts" / "fill_template.py"
DAY = 86400
T0 = 1_700_000_000


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    return mod


score = load(SCORE)
fill = load(FILL)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name).resolve() / "acme-web"
        self.repo.mkdir()

    def write(self, rel: str, text: str = "x = 1\n", mtime: int | None = None) -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        if mtime:
            os.utime(p, (mtime, mtime))
        return p

    def git(self, *args: str, when: int | None = None, cwd: Path | None = None):
        env = {"PATH": os.environ["PATH"], "HOME": self._tmp.name, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_AUTHOR_NAME": "user", "GIT_AUTHOR_EMAIL": "user@example.com",
               "GIT_COMMITTER_NAME": "user", "GIT_COMMITTER_EMAIL": "user@example.com"}
        if when:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{when} +0000"
        subprocess.run(["git", *args], cwd=cwd or self.repo, env=env, check=True, capture_output=True)

    def commit(self, rel: str, text: str, when: int):
        self.write(rel, text)
        self.git("add", rel)
        self.git("commit", "-q", "-m", "c", when=when)

    def cats(self, lang: str = "ko"):
        return score.build_report(self.repo, lang).categories


class PathRegex(Base):
    def test_extensions_are_not_truncated(self):
        for ref in ("src/app/page.tsx", "x/b.jsx", "lib/a.json", "a/b.ts", "a/b.js", "a/b.md", "./x.py"):
            self.assertEqual(score.find_path_refs(f"see `{ref}` here"), {ref})

    def test_longer_extension_is_not_cut_into_a_known_one(self):
        self.assertEqual(score.find_path_refs("data/rows.tsv data/app.jsonl"), set())

    def test_dot_and_hyphen_dirs_keep_their_first_segment(self):
        for ref in (".github/workflows/ci.yml", "my-app/src/main.py", "../shared/x.md"):
            self.assertEqual(score.find_path_refs(f"({ref})"), {ref})

    def test_urls_home_and_placeholders_are_not_repo_paths(self):
        text = "https://example.com/org/repo/blob/main/docs/a.md ~/.config/x.toml $HOME/a/b.json <dir>/a/b.py"
        self.assertEqual(score.find_path_refs(text), set())

    def test_existing_tsx_is_not_reported(self):
        self.write("src/app/page.tsx")
        self.write("AGENTS.md", "main file: src/app/page.tsx, gone: src/app/gone.tsx\n")
        e = self.cats()["E"].evidence
        self.assertEqual((e["ref_total"], e["broken_refs"]), (2, ["AGENTS.md: src/app/gone.tsx"]))

    def test_ref_relative_to_an_ancestor_dir(self):
        self.write("packages/ui/src/button.ts")
        self.write("packages/ui/docs/README.md", "see src/button.ts and ../src/button.ts\n")
        self.assertEqual(self.cats()["E"].evidence["ref_broken"], 0)


class Evidence(Base):
    def test_every_broken_ref_is_kept(self):
        """후보마다 판정하려면 근거 JSON에 하나도 빠지지 않아야 한다."""
        self.write("CLAUDE.md", "".join(f"`src/gone/f{i}.py`\n" for i in range(51)))
        e = self.cats()["E"].evidence
        self.assertEqual((e["ref_broken"], len(e["broken_refs"])), (51, 51))

    def test_checkout_location_does_not_change_the_score(self):
        totals = []
        for parent in ("plain", ".cache", "build"):
            self.repo = Path(self._tmp.name).resolve() / parent / "demo"
            self.write("agent-results.json", "{}")
            self.write("node_modules/x/agent-results.json", "{}")
            self.write("src/app.py")
            report = score.build_report(self.repo, "ko")
            self.assertEqual(report.categories["G"].evidence["metric_files"], ["agent-results.json"], parent)
            totals.append(report.total)
        self.assertEqual(len(set(totals)), 1, totals)


class RootContext(Base):
    def score_with(self, name: str) -> tuple[int, int, object]:
        self.write("app/main.py")
        p = self.write(name, "# Guide\n")
        r = score.build_report(self.repo)
        p.unlink()
        return r.total, r.categories["A"].score, r.categories["A"].evidence["root_context"]

    def test_agents_only_scores_like_claude_only(self):
        a, c = self.score_with("AGENTS.md"), self.score_with("CLAUDE.md")
        self.assertEqual(a[:2], c[:2])
        self.assertEqual((a[2], c[2]), ("AGENTS.md", "CLAUDE.md"))

    def test_agents_only_is_not_penalised(self):
        self.write("AGENTS.md", "# Guide\n")
        self.write("app/main.py")
        self.write("app/AGENTS.md", "# App\n")
        a = self.cats()["A"]
        self.assertEqual((a.score, a.findings), (15, []))

    def test_symlinked_pair_is_counted_once(self):
        self.write("AGENTS.md", "see app/gone.py\n")
        (self.repo / "CLAUDE.md").symlink_to("AGENTS.md")
        r = score.build_report(self.repo)
        self.assertEqual(r.meta["context_files_total"], 1)
        self.assertEqual(r.categories["E"].evidence["ref_broken"], 1)


class EmptyRepo(Base):
    def test_empty_repo(self):
        r = score.build_report(self.repo)
        a = r.categories["A"]
        self.assertEqual((a.score, a.evidence["core_modules"], r.meta["modules_total"]), (0, 0, 0))
        self.assertNotIn("0개:", " ".join(a.findings))
        self.assertEqual(r.grade, "AI-Hostile")
        self.assertEqual(fill.auto_values(score.serialize(r))["COVERED_MODULES"], "0")

    def test_missing_path_is_an_error(self):
        r = subprocess.run([sys.executable, "-I", str(SCORE), str(self.repo / "nope")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class SingleApp(Base):
    def rels(self):
        return [m.rel for m in score.find_core_modules(self.repo)]

    def test_domains_are_modules_and_src_keeps_the_rest(self):
        for d in ("cart", "login"):
            self.write(f"src/features/{d}/index.ts")
        self.write("src/lib/util.ts")
        self.assertEqual(self.rels(), ["src", "src/features/cart", "src/features/login"])
        self.assertEqual(score.find_core_modules(self.repo)[0].code_files, 1)

    def test_src_is_not_a_module_when_only_domains_hold_code(self):
        for d in ("cart", "login"):
            self.write(f"src/domains/{d}/index.ts")
        self.assertEqual(self.rels(), ["src/domains/cart", "src/domains/login"])

    def test_one_code_domain_is_not_expanded(self):
        self.write("src/modules/cart/index.ts")
        self.write("src/modules/assets/logo.txt")
        self.assertEqual(self.rels(), ["src"])

    def test_domains_inherit_the_src_guide(self):
        """src 안내 하나로 잘 적은 저장소가 도메인 인식 때문에 깎이지 않는다."""
        for d in ("cart", "login", "search"):
            self.write(f"src/features/{d}/index.ts")
        self.write("src/AGENTS.md", "# Purpose\n# Patterns\n# Dependencies\nNote: x\n")
        cats = self.cats()
        self.assertEqual((cats["A"].evidence["coverage_ratio"], cats["C"].score), (1.0, 16))

    def test_domain_docs_raise_coverage(self):
        self.write("AGENTS.md", "# Guide\n")
        for d in ("cart", "login", "search"):
            self.write(f"src/features/{d}/index.ts")
        self.assertEqual(self.cats()["A"].score, 0)
        for d in ("cart", "login", "search"):
            self.write(f"src/features/{d}/AGENTS.md", "# D\n")
        self.assertEqual(self.cats()["A"].score, 15)


class Freshness(Base):
    def f(self):
        return self.cats()["F"]

    def test_git_commit_time_wins_over_mtime(self):
        """clone하면 파일 시각은 모두 같다. 커밋 시각으로는 낡았다."""
        self.git("init", "-q")
        self.commit("app/AGENTS.md", "# A\n", T0)
        self.commit("app/sub/main.py", "x = 1\n", T0 + 60 * DAY)
        for p in ("app/AGENTS.md", "app/sub/main.py"):
            os.utime(self.repo / p, (T0, T0))
        e = self.f().evidence
        self.assertEqual((e["time_basis"], e["drifted_modules"]), ("git", 1))

    def test_old_mtime_alone_is_not_drift_in_git(self):
        self.git("init", "-q")
        self.commit("app/AGENTS.md", "# A\n", T0)
        self.commit("app/main.py", "x = 1\n", T0 + DAY)
        os.utime(self.repo / "app/AGENTS.md", (T0 - 400 * DAY, T0 - 400 * DAY))
        e = self.f().evidence
        self.assertEqual((e["time_basis"], e["drifted_modules"]), ("git", 0))

    def test_without_git_uses_mtime_and_says_so(self):
        self.write("app/AGENTS.md", "# A\n", mtime=T0)
        self.write("app/main.py", mtime=T0 + 60 * DAY)
        f = self.f()
        self.assertEqual((f.evidence["time_basis"], f.evidence["drifted_modules"]), ("mtime", 1))
        self.assertTrue(any("mtime" in x for x in f.findings))

    def test_symlinked_guide_uses_the_target_commit(self):
        self.git("init", "-q")
        (self.repo / "app").mkdir()
        (self.repo / "app/CLAUDE.md").symlink_to("AGENTS.md")
        self.git("add", "app/CLAUDE.md")
        self.git("commit", "-q", "-m", "c", when=T0)
        self.commit("app/main.py", "x = 1\n", T0 + 60 * DAY)
        self.commit("app/AGENTS.md", "# A\n", T0 + 60 * DAY)
        e = self.f().evidence
        self.assertEqual((e["time_basis"], e["drifted_modules"]), ("git", 0))

    def test_uncommitted_module_is_marked(self):
        self.git("init", "-q")
        self.commit("app/AGENTS.md", "# A\n", T0)
        self.commit("app/main.py", "x = 1\n", T0)
        self.write("new/AGENTS.md", "# N\n")
        self.write("new/main.py")
        self.assertEqual(self.f().evidence["time_basis"], "git+mtime")

    def test_shallow_clone_is_not_judged(self):
        self.git("init", "-q")
        self.commit("app/AGENTS.md", "# A\n", T0)
        self.commit("app/main.py", "x = 1\n", T0 + 60 * DAY)
        dst = Path(self._tmp.name) / "shallow"
        self.git("clone", "-q", "--depth", "1", self.repo.as_uri(), str(dst), cwd=Path(self._tmp.name))
        f = score.build_report(dst).categories["F"]
        self.assertEqual((f.evidence["time_basis"], f.score), ("shallow", 3))


class Lang(Base):
    def run_cli(self, lang: str | None):
        out = self.repo.parent / f"{lang}.json"
        cmd = [sys.executable, "-I", str(SCORE), str(self.repo), "--json", str(out)] + (["--lang", lang] if lang else [])
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return r.stdout, json.loads(out.read_text(encoding="utf-8"))

    def test_english_output_has_no_korean_and_same_scores(self):
        self.write("app/main.py", "x = 1\n" * 600)
        self.write("README.md", "see app/gone.py\n" * 120)
        en_out, en = self.run_cli("en")
        ko_out, ko = self.run_cli(None)
        self.assertIsNone(re.search("[가-힣]", en_out + json.dumps(en, ensure_ascii=False)))
        self.assertIsNotNone(re.search("[가-힣]", ko_out))
        self.assertEqual((ko["meta"]["lang"], en["meta"]["lang"]), ("ko", "en"))
        self.assertEqual({k: c["score"] for k, c in en["categories"].items()},
                         {k: c["score"] for k, c in ko["categories"].items()})
        self.assertIsNone(re.search("[가-힣]", "".join(v for v in fill.auto_values(en).values())))

    def test_json_keeps_no_absolute_path(self):
        self.write("app/main.py")
        _, data = self.run_cli("ko")
        self.assertNotIn(str(self.repo.parent), json.dumps(data))

    def test_messages_have_the_same_fields_in_both_languages(self):
        fields = lambda s: sorted({f for _, f, _, _ in string.Formatter().parse(s) if f})
        for key, (ko, en) in score.MSG.items():
            self.assertEqual(fields(ko), fields(en), key)
            self.assertIsNone(re.search("[가-힣]", en), key)


class Actions(Base):
    def test_effort_is_bounded_and_label_matches_hours(self):
        for i in range(40):
            self.write(f"app/f{i}.py", "x = 1\n" * 501)
        for a in score.build_report(self.repo).actions:
            self.assertEqual(a.effort, score.effort_label(a.effort_hours))
            self.assertLessEqual(a.effort_hours, 10)


class Template(Base):
    TEXT = (ROOT / "assets" / "template.html").read_text(encoding="utf-8")
    SLOTS = set(fill.RE_SLOT.findall(TEXT))

    def skill_table(self) -> dict[str, set[str]]:
        by = {"스크립트": set(), "나": set()}
        for line in (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 3 and cells[1] in by:
                for name in re.findall(r"\{\{([A-Z_*]+)\}\}", cells[0]):
                    by[cells[1]] |= {f"{k}{name[1:]}" for k in "ABCDEFG"} if name.startswith("X_") else {name}
        return by

    def test_skill_table_matches_template_one_to_one(self):
        by = self.skill_table()
        auto = (by["스크립트"] - {"T_*"}) | {s for s in self.SLOTS if s.startswith("T_")}
        self.assertEqual(auto | by["나"], self.SLOTS)
        self.assertEqual(auto & by["나"], set())

    def test_script_fills_exactly_the_slots_the_table_gives_it(self):
        values = set(fill.auto_values(score.serialize(score.build_report(self.repo))))
        self.assertEqual(self.SLOTS - values, self.skill_table()["나"])
        self.assertEqual(values - self.SLOTS, set())

    def test_template_holds_no_concrete_data(self):
        body = self.TEXT[self.TEXT.index("<body>"):]
        self.assertIsNone(re.search(r"20\d\d-\d\d-\d\d", body))
        self.assertIsNone(re.search(r"[\w/]+\.(?:tsx?|jsx?|py|sql|go|rs)\b", body))
        self.assertIsNone(re.search(r"\b(?:feat|fix|main|master)/", body))
        self.assertIsNone(re.search("[가-힣]", self.TEXT))

    def test_fill_then_check(self):
        self.write("app/main.py")
        data, out = self.repo.parent / "s.json", self.repo.parent / "map.html"
        data.write_text(json.dumps(score.serialize(score.build_report(self.repo, "en"))), encoding="utf-8")
        run = lambda *a: subprocess.run([sys.executable, "-I", str(FILL), *map(str, a)], capture_output=True, text=True)
        self.assertEqual(run(data, "-o", out).returncode, 0)
        r = run("--check", out)
        self.assertEqual(r.returncode, 1)
        self.assertIn("남은 자리 10개", r.stdout)
        out.write_text(fill.RE_SLOT.sub("ok", out.read_text(encoding="utf-8")), encoding="utf-8")
        self.assertEqual(run("--check", out).returncode, 0)

    def test_check_catches_misspelled_slots(self):
        self.assertEqual(fill.remaining("a\n{{score desc}} {{A_NOTE"), [(2, "{{score desc}}"), (2, "{{A_NOTE")])

    def test_refuses_to_write_the_template_itself(self):
        data = self.repo.parent / "s.json"
        data.write_text(json.dumps(score.serialize(score.build_report(self.repo))), encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", str(FILL), str(data), "-o", str(fill.TEMPLATE)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(fill.TEMPLATE.read_text(encoding="utf-8"), self.TEXT)

    def test_values_are_escaped(self):
        data = score.serialize(score.build_report(self.repo))
        data["meta"]["repo"] = "<b>x</b>"
        self.assertEqual(fill.auto_values(data)["REPO_NAME"], "&lt;b&gt;x&lt;/b&gt;")


class SkillFile(unittest.TestCase):
    def test_frontmatter_and_length(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        head = text.split("---")[1]
        self.assertIn(f"name: {ROOT.name}\n", head)
        self.assertLessEqual(len(re.search(r"^description: (.+)$", head, re.M).group(1)), 350)
        self.assertLessEqual(len(text.splitlines()), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
