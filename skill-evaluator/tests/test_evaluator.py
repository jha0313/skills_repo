import copy
import json
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import adapters
import core
import evaluate
from discovery import discover, snapshot_hash
from reporting import publish, write_reports

FIXTURES = Path(__file__).parent / "fixtures"


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.case = core.read_data(FIXTURES / "basic.yaml")["test_cases"][0]
        self.execution = {
            "conversation": "USER PROMPT includes fake answer",
            "response": "Welcome to Observatory.",
            "tool_calls": [
                {
                    "name": "Skill",
                    "input": {"skill": "evaluated-skill:observatory-greeting"},
                }
            ],
            "metadata": {
                "model": "test",
                "started_at": "t0",
                "finished_at": "t1",
                "duration_seconds": 1,
                "exit_state": "completed",
                "timed_out": False,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "cost_usd": None,
                "cost_basis": "unknown",
                "skill_invocations": ["evaluated-skill:observatory-greeting"],
            },
            "artifacts": {"files": [], "urls": []},
        }
        d = self.root / "cases/TC-001"
        d.mkdir(parents=True)
        (d / "response.txt").write_text("Welcome to Observatory.\n")
        core.write_json(d / "metadata.json", self.execution["metadata"])
        core.write_json(d / "tool_calls.json", self.execution["tool_calls"])

    def tearDown(self):
        self.tmp.cleanup()

    def judgment(self, binary=False, score=None):
        v = (1 if binary else 5) if score is None else score
        item = {
            "score": v,
            "rubric_level": v,
            "evidence": [
                {
                    "path": "cases/TC-001/response.txt",
                    "line_start": 1,
                    "line_end": 1,
                    "quote": "Welcome to Observatory.",
                }
            ],
        }
        return {
            "case_id": "TC-001",
            "dimensions": {d: copy.deepcopy(item) for d in core.DIMENSIONS[:4]},
            "best_practice_subcriteria": {d: copy.deepcopy(item) for d in core.BP},
            "business_impact_subcriteria": {d: copy.deepcopy(item) for d in core.BI},
            "semantic_checks": [dict(copy.deepcopy(item), index=0)],
        }

    def test_exact_mode_distributions(self):
        for f, mode, binary in [
            ("basic", "basic", False),
            ("basic-binary", "basic", True),
            ("thorough", "thorough", False),
        ]:
            core.validate_criteria(core.read_data(FIXTURES / f"{f}.yaml"), mode, binary)
        self.assertEqual(core.DISTRIBUTIONS["deep"], (7, 4, 7, 5, 7))
        broken = core.read_data(FIXTURES / "basic.yaml")
        broken["test_cases"].append(broken["test_cases"][0])
        with self.assertRaises(core.EvalError):
            core.validate_criteria(broken, "basic", False)

    def test_binary_and_default_flags(self):
        self.assertTrue(
            evaluate.resolved_options(
                evaluate.parser().parse_args(["run", "x", "--binary"])
            )["binary"]
        )
        self.assertFalse(
            evaluate.resolved_options(evaluate.parser().parse_args(["run", "x"]))[
                "binary"
            ]
        )

    def test_backup_preserves_exact_old_bytes(self):
        p = self.root / "evals/eval_criteria.yaml"
        p.parent.mkdir()
        p.write_text("old criteria\n")
        backup = core.backup_write(p, {"new": 1})
        self.assertEqual(Path(backup).read_text(), "old criteria\n")
        backup2 = core.backup_write(p, {"next": 2})
        self.assertNotEqual(backup, backup2)

    def test_invocation_forced_context_rejected(self):
        for update in (
            {"forced_context": True},
            {"prompt": "Use /observatory-greeting now"},
        ):
            data = core.read_data(FIXTURES / "basic.yaml")
            data["test_cases"][0].update(update)
            with self.assertRaises(core.EvalError):
                core.validate_criteria(data, "basic", False)

    def test_semantic_rubric_malformed(self):
        data = core.read_data(FIXTURES / "basic-binary.yaml")
        data["test_cases"][0]["quality_criteria"]["semantic_checks"][0]["rubric"][
            "5"
        ] = "bad"
        with self.assertRaises(core.EvalError):
            core.validate_criteria(data, "basic", True)

    def test_prompt_and_tool_payload_not_response_evidence(self):
        case = copy.deepcopy(self.case)
        case["eval_target"] = "response"
        e = copy.deepcopy(self.execution)
        e["response"] = "wrong"
        e["conversation"] = "Welcome to Observatory."
        self.assertEqual(
            core.deterministic_checks(case, e)["required_present_misses"],
            ["Welcome to Observatory."],
        )

    def test_citation_correctness_and_case_isolation(self):
        j = self.judgment()
        core.validate_judgment(j, {**self.case, "_mode": "basic"}, False, self.root)
        for path in (
            "criteria.yaml",
            "cases/TC-002/response.txt",
            "cases/TC-001/conversation.txt",
            "../outside.txt",
        ):
            bad = copy.deepcopy(j)
            bad["dimensions"]["invocation"]["evidence"][0]["path"] = path
            with self.assertRaises(core.EvalError):
                core.validate_judgment(
                    bad, {**self.case, "_mode": "basic"}, False, self.root
                )
        bad = copy.deepcopy(j)
        bad["dimensions"]["invocation"]["evidence"][0]["line_start"] = 2
        with self.assertRaises(core.EvalError):
            core.validate_judgment(
                bad, {**self.case, "_mode": "basic"}, False, self.root
            )

    def test_citation_allowlist_matches_judge_contract(self):
        # Harness records (tool_calls.json, metadata.json, artifacts.json) are always
        # citable; target content (response.txt, artifacts/*) stays gated by eval_target.
        d = self.root / "cases/TC-001"
        core.write_json(
            d / "artifacts.json", {"files": [{"path": "notes.txt", "sha256": "ab"}]}
        )
        (d / "artifacts").mkdir()
        (d / "artifacts/notes.txt").write_text("alpha: first\n")

        def cite(path, quote):
            # Every scored item cites the same file so only the allowlist is under test.
            j = self.judgment()
            ev = [{"path": path, "line_start": 1, "line_end": 1, "quote": quote}]
            for group in (
                "dimensions",
                "best_practice_subcriteria",
                "business_impact_subcriteria",
            ):
                for item in j[group].values():
                    item["evidence"] = copy.deepcopy(ev)
            for item in j["semantic_checks"]:
                item["evidence"] = copy.deepcopy(ev)
            return j

        for target, path, quote, ok in (
            ("response", "cases/TC-001/tool_calls.json", "[", True),
            ("response", "cases/TC-001/metadata.json", "{", True),
            ("response", "cases/TC-001/artifacts.json", "{", True),
            ("response", "cases/TC-001/artifacts/notes.txt", "alpha", False),
            ("all", "cases/TC-001/artifacts/notes.txt", "alpha", True),
            ("tool_usage", "cases/TC-001/response.txt", "Welcome", False),
            ("tool_usage", "cases/TC-001/artifacts.json", "{", True),
        ):
            case = {**copy.deepcopy(self.case), "eval_target": target, "_mode": "basic"}
            case["category"] = "efficiency"
            if ok:
                core.validate_judgment(cite(path, quote), case, False, self.root)
            else:
                with self.assertRaises(core.EvalError):
                    core.validate_judgment(cite(path, quote), case, False, self.root)

    def test_judge_packet_excludes_uncitable_transcript(self):
        d = self.root / "cases/TC-001"
        (d / "conversation.txt").write_text("USER PROMPT\nraw trace\n")
        core.write_json(d / "artifacts.json", {"files": []})
        packet = evaluate.evidence_packet(self.root, self.case)
        self.assertEqual(
            set(packet),
            {
                "cases/TC-001/response.txt",
                "cases/TC-001/tool_calls.json",
                "cases/TC-001/metadata.json",
                "cases/TC-001/artifacts.json",
            },
        )

    def test_judge_rounds_checkpoint_valid_rounds_and_retry_once(self):
        options = {
            "judge_rounds": 3,
            "concurrency": 1,
            "mode": "basic",
            "binary": False,
        }
        batch = [self.case]
        calls = []

        def flaky(run, cases, manifest, idx, rn):
            calls.append(rn)
            if rn == 2 and calls.count(2) == 1:
                raise core.EvalError("Evidence quote is not present at cited lines")
            return {"TC-001": self.judgment()}, {"cost_usd": 1.0}

        rounds, costs = evaluate.judge_rounds(
            self.root, batch, {}, 0, options, judge=flaky
        )
        self.assertEqual((len(rounds), calls.count(2)), (3, 2))
        self.assertIn(
            "retried_after",
            core.read_data(self.root / "judges/batch-000-round-2/validated.json"),
        )
        # Raw attempts never overwrite each other.
        (self.root / "judges/batch-000-round-2").mkdir(exist_ok=True)
        self.assertEqual(
            evaluate.judge_attempt_dir(self.root, 0, 2).name,
            "batch-000-round-2-retry-1",
        )
        # A round invalid twice is an infrastructure error; valid rounds stay checkpointed.
        root2 = self.root / "run2"
        (root2 / "cases/TC-001").mkdir(parents=True)
        (root2 / "cases/TC-001/response.txt").write_text("Welcome to Observatory.\n")

        def broken(run, cases, manifest, idx, rn):
            if rn == 1:
                raise core.EvalError("bad citation")
            return {"TC-001": self.judgment()}, {"cost_usd": 1.0}

        with self.assertRaises(core.EvalError):
            evaluate.judge_rounds(root2, batch, {}, 0, options, judge=broken)
        self.assertTrue((root2 / "judges/batch-000-round-3/validated.json").exists())
        self.assertFalse((root2 / "judges/batch-000-round-1/validated.json").exists())
        # Resume reuses the two checkpoints and re-judges only the missing round.
        again = []

        def fixed(run, cases, manifest, idx, rn):
            again.append(rn)
            return {"TC-001": self.judgment()}, {"cost_usd": 1.0}

        rounds, _ = evaluate.judge_rounds(root2, batch, {}, 0, options, judge=fixed)
        self.assertEqual((len(rounds), again), (3, [1]))

    def test_citation_tolerates_small_line_slip_but_not_fabrication(self):
        path = self.root / "cases/TC-001/tool_calls.json"
        lines = [f"line {i}" for i in range(1, 11)]
        lines[6] = '      "description": "Probe functions with uncovered inputs"'
        path.write_text("\n".join(lines) + "\n")
        quote = "Probe functions with uncovered inputs"
        rel = "cases/TC-001/tool_calls.json"
        # Exact line, and one or two lines off, are all the same real evidence.
        for start in (7, 6, 5, 8, 9):
            core.verify_citation(
                {"path": rel, "line_start": start, "line_end": start, "quote": quote},
                self.root,
            )
        # Three lines away is no longer a slip; a mangled quote is never accepted.
        for bad in (
            {"path": rel, "line_start": 4, "line_end": 4, "quote": quote},
            {"path": rel, "line_start": 10, "line_end": 10, "quote": quote},
            {
                "path": rel,
                "line_start": 7,
                "line_end": 7,
                "quote": "Probe functions with covered inputs",
            },
        ):
            with self.assertRaises(core.EvalError):
                core.verify_citation(bad, self.root)
        # A judge that normalises a Korean verb ending still points at real evidence.
        lines[3] = (
            "`git worktree add`는 base revision을 요구하므로 **원리적으로 불가능**합니다."
        )
        path.write_text("\n".join(lines) + "\n")
        core.verify_citation(
            {
                "path": rel,
                "line_start": 4,
                "line_end": 4,
                "quote": "`git worktree add`는 base revision을 요구하므로 **원리적으로 불가능**입니다.",
            },
            self.root,
        )
        # A flipped verdict word or an invented sentence is not a slip.
        lines[8] = "GATE result: 4 tests passed, exit 0"
        path.write_text("\n".join(lines) + "\n")
        for bad_quote in (
            "GATE result: 4 tests failed, exit 0",
            "GATE result: all tests skipped",
        ):
            with self.assertRaises(core.EvalError):
                core.verify_citation(
                    {"path": rel, "line_start": 9, "line_end": 9, "quote": bad_quote},
                    self.root,
                )

    def test_judge_rounds_reuse_checkpoints_after_batches_shift(self):
        """After a resume, graded cases leave their batch and indices shift; validated
        rounds must still be reused when they cover the batch, wherever they sit."""
        options = {
            "judge_rounds": 3,
            "concurrency": 1,
            "mode": "basic",
            "binary": False,
        }
        case2 = copy.deepcopy(self.case)
        case2["id"] = "TC-002"
        d = self.root / "cases/TC-002"
        d.mkdir(parents=True)
        for name in (
            "response.txt",
            "tool_calls.json",
            "metadata.json",
            "artifacts.json",
        ):
            src = self.root / "cases/TC-001" / name
            (d / name).write_text(src.read_text() if src.exists() else "{}")

        def judgment_for(cid):
            return json.loads(json.dumps(self.judgment()).replace("TC-001", cid))

        # Original grading: batch index 1 held both cases; rounds 2 and 3 validated.
        for rn in (2, 3):
            core.write_json(
                self.root / f"judges/batch-001-round-{rn}/validated.json",
                {
                    "case_ids": ["TC-001", "TC-002"],
                    "judgments": {
                        "TC-001": judgment_for("TC-001"),
                        "TC-002": judgment_for("TC-002"),
                    },
                    "usage": {"cost_usd": 1.0},
                },
            )
        calls = []

        def judge(run, cases, manifest, idx, rn):
            calls.append((idx, rn, [c["id"] for c in cases]))
            return {c["id"]: judgment_for(c["id"]) for c in cases}, {"cost_usd": 1.0}

        # Resume: TC-001 already graded, so TC-002 is now alone at batch index 0.
        rounds, costs = evaluate.judge_rounds(
            self.root, [case2], {}, 0, options, judge=judge
        )
        self.assertEqual(calls, [(0, 1, ["TC-002"])])
        self.assertEqual(len(rounds), 3)
        self.assertTrue(all(set(r) == {"TC-002"} for r in rounds))
        # The original checkpoints are left untouched.
        old = core.read_data(self.root / "judges/batch-001-round-2/validated.json")
        self.assertEqual(old["case_ids"], ["TC-001", "TC-002"])

    def test_judge_checkpoint_never_overwrites_another_batch(self):
        """The validated checkpoint is written beside the raw attempt that produced it,
        so a re-batched resume cannot clobber a different batch's checkpoint."""
        options = {
            "judge_rounds": 1,
            "concurrency": 1,
            "mode": "basic",
            "binary": False,
        }
        other = self.root / "judges/batch-000-round-1"
        core.write_json(
            other / "validated.json",
            {"case_ids": ["TC-009"], "judgments": {}, "usage": {"cost_usd": 1.0}},
        )

        def judge(run, cases, manifest, idx, rn):
            out = evaluate.judge_attempt_dir(run, idx, rn)
            out.mkdir(parents=True)
            return {"TC-001": self.judgment()}, {
                "cost_usd": 1.0,
                "judge_dir": str(out.relative_to(run)),
            }

        rounds, _ = evaluate.judge_rounds(
            self.root, [self.case], {}, 0, options, judge=judge
        )
        self.assertEqual(len(rounds), 1)
        self.assertEqual(
            core.read_data(other / "validated.json")["case_ids"], ["TC-009"]
        )
        mine = self.root / "judges/batch-000-round-1-retry-1/validated.json"
        self.assertEqual(core.read_data(mine)["case_ids"], ["TC-001"])
        # ...and that checkpoint is found again on the next pass without a judge call.
        rounds, _ = evaluate.judge_rounds(
            self.root,
            [self.case],
            {},
            0,
            options,
            judge=lambda *a: (_ for _ in ()).throw(
                AssertionError("no judge call expected")
            ),
        )
        self.assertEqual(len(rounds), 1)

    def test_regrade_imports_executions_and_records_provenance(self):
        """A regrade run copies execution evidence from a finished or interrupted run,
        re-hashes it, keeps unexecuted cases pending, and never touches the target."""
        source = self.root / "source-run"
        (source / "cases/TC-001").mkdir(parents=True)
        for name in (
            "conversation.txt",
            "response.txt",
            "metadata.json",
            "artifacts.json",
            "tool_calls.json",
            "prompt.json",
        ):
            (source / "cases/TC-001" / name).write_text(
                (self.root / "cases/TC-001" / name).read_text()
                if (self.root / "cases/TC-001" / name).exists()
                else "{}"
            )
        core.write_json(source / "cases/TC-001/execution.json", self.execution)
        criteria = core.read_data(FIXTURES / "basic.yaml")
        criteria = core.validate_criteria(criteria, "basic", False)
        core.write_json(source / "criteria.yaml", criteria)
        core.write_json(
            source / "analysis.json", {"name": "observatory-greeting", "mutates": False}
        )
        options = {"mode": "basic", "binary": False, "judge_rounds": 3}
        skill_dir = FIXTURES / "observatory-greeting"
        manifest = {
            "run_id": "old-run",
            "criteria_hash": core.digest(criteria),
            "options": options,
            "options_hash": core.digest(options),
            "skill": {
                "installed_path": str(skill_dir),
                "skill_hash": "not-the-real-hash",
            },
            "evaluator_hash": "old-evaluator",
            "cases": {c["id"]: {"state": "pending"} for c in criteria["test_cases"]},
            "author_usage": {"cost_usd": 3.0},
            "config": {},
            "config_hash": core.digest({}),
        }
        manifest["cases"]["TC-001"] = {"state": "executed"}
        core.write_json(source / "manifest.json", manifest)

        args = types.SimpleNamespace(
            regrade=str(source),
            output=str(self.root / "regrade-run"),
            **{
                k: None
                for k in (
                    "basic",
                    "deep",
                    "binary",
                    "local",
                    "no_visualize",
                    "model",
                    "judge_model",
                    "timeout",
                    "judge_timeout",
                    "concurrency",
                    "judge_rounds",
                    "allow_tool",
                    "config",
                    "criteria",
                    "source",
                    "target",
                )
            },
        )

        # A pending case with a changed skill would mix revisions.
        with self.assertRaises(core.EvalError):
            evaluate.regrade(args)
        manifest["skill"]["skill_hash"] = evaluate.snapshot_hash(skill_dir)
        core.write_json(source / "manifest.json", manifest)
        run, new_manifest, new_criteria, _ = evaluate.regrade(args)
        self.assertEqual(run, (self.root / "regrade-run").resolve())
        self.assertEqual(new_manifest["cases"]["TC-001"]["state"], "executed")
        self.assertIn("evidence_hashes", new_manifest["cases"]["TC-001"])
        self.assertEqual(new_manifest["cases"]["TC-002"]["state"], "pending")
        self.assertEqual(new_manifest["regrade_of"]["run_id"], "old-run")
        self.assertEqual(
            new_manifest["regrade_of"]["evaluator_hash_at_execution"], "old-evaluator"
        )
        self.assertEqual(new_manifest["regrade_of"]["imported_cases"], ["TC-001"])
        self.assertNotEqual(new_manifest["run_id"], "old-run")
        self.assertEqual(new_manifest["criteria_hash"], core.digest(new_criteria))
        self.assertEqual(new_manifest["author_usage"]["cost_usd"], 0)
        self.assertTrue((run / "cases/TC-001/execution.json").exists())
        core.verify_evidence_hashes(
            run, new_manifest["cases"]["TC-001"]["evidence_hashes"]
        )

    def test_binary_thresholds_weighted_and_labels(self):
        case = core.read_data(FIXTURES / "basic-binary.yaml")["test_cases"][0]
        j = self.judgment(True)
        for d in core.BP[:2]:
            j["best_practice_subcriteria"][d]["score"] = 0
        for d in core.BI[:2]:
            j["business_impact_subcriteria"][d]["score"] = 0
        result = core.grade_case(case, self.execution, [j] * 3, True, "basic")
        self.assertEqual(result["verdict"], "PASS")
        self.assertNotIn("grade", result)
        self.assertEqual(set(result["dimension_verdicts"].values()), {"PASS"})
        self.assertEqual(result["score"], 1)
        case["quality_criteria"]["semantic_checks"] *= 2
        j["semantic_checks"].append({**j["semantic_checks"][0], "index": 1, "score": 0})
        case["quality_criteria"]["semantic_checks"][1]["weight"] = 1
        result = core.grade_case(case, self.execution, [j] * 3, True, "basic")
        self.assertEqual(result["verdict"], "FAIL")

    def test_likert_thresholds(self):
        self.assertEqual(
            [core.letter(v) for v in (4.5, 4.49, 3.5, 3, 2, 1)],
            ["A", "B", "B", "C", "D", "F"],
        )
        result = core.grade_case(
            self.case, self.execution, [self.judgment()] * 3, False, "basic"
        )
        self.assertEqual(result["grade"], "A")

    def test_critical_failure_cannot_average_away(self):
        e = copy.deepcopy(self.execution)
        e["response"] = "Wrong greeting"
        result = core.grade_case(self.case, e, [self.judgment()] * 3, False, "basic")
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["verdict"], "FAIL")

    def test_missing_artifact(self):
        case = copy.deepcopy(self.case)
        case["quality_criteria"]["artifact_checks"] = [{"path": "missing.md"}]
        self.assertEqual(
            core.deterministic_checks(case, self.execution)["missing_artifacts"],
            ["missing.md"],
        )

    def test_adapter_normalization_matches(self):
        local = core.normalize_execution(self.execution, "local")
        msl = core.normalize_execution(self.execution, "msl")
        local["metadata"].pop("adapter")
        msl["metadata"].pop("adapter")
        self.assertEqual(local, msl)

    def test_unknown_cost_and_timeout_preserved(self):
        e = copy.deepcopy(self.execution)
        e["metadata"]["timed_out"] = True
        normalized = core.normalize_execution(e, "local")
        self.assertTrue(normalized["metadata"]["timed_out"])
        self.assertIsNone(normalized["metadata"]["cost_usd"])

    def test_empty_transcript_error_no_score(self):
        result = core.error_case(self.case, "Empty execution transcript")
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIsNone(result["score"])

    def test_mock_requires_data_and_verified_runtime(self):
        data = core.read_data(FIXTURES / "basic.yaml")
        data["test_cases"][0]["intercept_patterns"] = ["meta status"]
        with self.assertRaises(core.EvalError):
            core.validate_criteria(data, "basic", False)

    def test_dirty_source_never_modified_by_discovery(self):
        import shutil

        source = self.root / "source"
        shutil.copytree(FIXTURES / "observatory-greeting", source)
        (source / "unrelated.txt").write_text("dirty user work")
        before = snapshot_hash(source)
        discover(str(source))
        self.assertEqual(snapshot_hash(source), before)

    def test_native_routing_not_forced(self):
        analysis = discover(str(FIXTURES / "observatory-greeting"))
        stage = adapters.native_stage(
            analysis, self.case, self.root / "case", {"timeout": 120}
        )
        native = core.read_data(stage / "skill-evaluator-cases/TC-001/case.yaml")
        self.assertNotIn("append_system_prompt", native["execution"])

    def test_scaffold_script_is_staged_beside_case_yaml(self):
        # The native runner resolves context.scaffold_script relative to the case directory.
        fixture = self.root / "fixture"
        fixture.mkdir()
        (fixture / "notes.txt").write_text("alpha: first\n")
        analysis = discover(str(FIXTURES / "observatory-greeting"))
        case = dict(self.case, working_directory=str(fixture))
        stage = adapters.native_stage(
            analysis, case, self.root / "case", {"timeout": 120}
        )
        case_dir = stage / "skill-evaluator-cases/TC-001"
        native = core.read_data(case_dir / "case.yaml")
        script = case_dir / native["context"]["scaffold_script"]
        self.assertTrue(script.is_file())
        self.assertIn(str(stage / "fixture"), script.read_text())
        self.assertTrue((stage / "fixture/notes.txt").is_file())

    def test_idempotent_publisher_and_config_required(self):
        with self.assertRaises(core.EvalError):
            publish(self.root, {"run_id": "test"}, {}, "skillwatch")
        core.write_json(
            self.root / "skillwatch-receipt.json",
            {
                "payload_hash": core.digest({"run_id": "test"}),
                "idempotency_key": "test",
            },
        )
        self.assertEqual(
            publish(self.root, {"run_id": "test"}, {}, "skillwatch")["idempotency_key"],
            "test",
        )

    def test_native_trace_separates_loaded_skill_from_output(self):
        text = "\n".join(
            json.dumps(e)
            for e in [
                {
                    "type": "user",
                    "message": {"content": [{"type": "text", "text": "SECRET ANSWER"}]},
                },
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "actual answer"}]},
                },
                {"type": "result", "result": "actual answer"},
            ]
        )
        self.assertEqual(adapters.parse_trace(text)[4], "actual answer")

    def test_protected_artifact_requires_matching_hash(self):
        case = copy.deepcopy(self.case)
        case["quality_criteria"]["artifact_checks"] = [
            {"path": "USER_NOTES.md", "sha256": "a" * 64}
        ]
        e = copy.deepcopy(self.execution)
        e["artifacts"]["files"] = [
            {"path": "USER_NOTES.md", "exists": True, "sha256": "b" * 64}
        ]
        checks = core.deterministic_checks(case, e)
        self.assertEqual(checks["missing_artifacts"], [])
        self.assertEqual(checks["artifact_hash_mismatches"], ["USER_NOTES.md"])
        result = core.grade_case(case, e, [self.judgment()] * 3, False, "basic")
        self.assertTrue(result["critical_failure"])
        self.assertEqual(result["verdict"], "FAIL")
        e["artifacts"]["files"][0]["sha256"] = "a" * 64
        self.assertEqual(
            core.deterministic_checks(case, e)["artifact_hash_mismatches"], []
        )
        case["quality_criteria"]["artifact_checks"][0]["sha256"] = "not-hex"
        data = core.read_data(FIXTURES / "basic.yaml")
        data["test_cases"][0] = case
        with self.assertRaises(core.EvalError):
            core.validate_criteria(data, "basic", False)

    def test_native_trace_preserves_worker_attribution(self):
        # Judges may only cite tool_calls.json, so actor attribution, lineage and the
        # raw trace coordinate must survive normalization and citation verification.
        def use(tool_id, name):
            return {"type": "tool_use", "id": tool_id, "name": name, "input": {}}

        events = [
            {"type": "system", "subtype": "init"},
            {
                "type": "assistant",
                "parent_tool_use_id": None,
                "message": {"content": [use("toolu_parent_read", "Read")]},
            },
            {
                "type": "assistant",
                "parent_tool_use_id": None,
                "message": {"content": [use("toolu_agent", "Agent")]},
            },
            {
                "type": "assistant",
                "parent_tool_use_id": "toolu_agent",
                "message": {"content": [use("toolu_child_read", "Read")]},
            },
            {
                "type": "assistant",
                "parent_tool_use_id": "toolu_never_spawned",
                "message": {"content": [use("toolu_orphan", "Grep")]},
            },
            {
                "type": "assistant",
                "message": {"content": [use("toolu_unknown", "Read")]},
            },
            {"type": "result", "result": "done"},
        ]
        calls = adapters.parse_trace("\n".join(json.dumps(e) for e in events))[3]
        self.assertEqual(
            [
                (c["name"], c["actor"], c["parent_tool_use_id"], c["lineage_verified"])
                for c in calls
            ],
            [
                ("Read", "parent", None, None),
                ("Agent", "parent", None, None),
                ("Read", "worker", "toolu_agent", True),
                ("Grep", "worker", "toolu_never_spawned", False),
                ("Read", "unknown", None, None),
            ],
        )
        self.assertEqual([c["trace_line"] for c in calls], [2, 3, 4, 5, 6])
        core.write_json(self.root / "cases/TC-001/tool_calls.json", calls)
        lines = (self.root / "cases/TC-001/tool_calls.json").read_text().splitlines()
        worker_line = next(
            i for i, line in enumerate(lines, 1) if '"toolu_child_read"' in line
        )
        core.verify_citation(
            {
                "path": "cases/TC-001/tool_calls.json",
                "line_start": worker_line,
                "line_end": worker_line + 4,
                "quote": '"actor": "worker"',
            },
            self.root,
        )

    def test_process_timeout_stops_children(self):
        adapters.reset_cancellation()
        r = adapters.run_process(
            [sys.executable, "-c", "import time;time.sleep(10)"],
            self.root,
            0.1,
            self.root / "timeout",
        )
        self.assertTrue(r["timed_out"])
        self.assertLess(r["duration_seconds"], 2)

    def test_signal_cancels_active_and_queued_processes(self):
        script = self.root / "interrupt.py"
        script.write_text(
            """import concurrent.futures,signal,sys\nfrom pathlib import Path\nsys.path.insert(0,"""
            + repr(str(SCRIPTS))
            + """)\nfrom adapters import run_process,cancel_processes\ndef stop(*a):\n cancel_processes()\n raise KeyboardInterrupt\nsignal.signal(signal.SIGINT,stop)\ntry:\n with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:\n  jobs=[pool.submit(run_process,[sys.executable,'-c','import time;time.sleep(10)'],Path.cwd(),20,Path('log'+str(i))) for i in range(2)]\n  for f in jobs:f.result()\nexcept KeyboardInterrupt:sys.exit(130)\n"""
        )
        child = subprocess.Popen([sys.executable, str(script)], cwd=self.root)
        time.sleep(0.25)
        start = time.monotonic()
        child.send_signal(signal.SIGINT)
        child.wait(timeout=3)
        self.assertEqual(child.returncode, 130)
        self.assertLess(time.monotonic() - start, 2)

    def test_parent_plugin_custom_eval_directory_is_not_selected(self):
        source = self.root / "plugin"
        (source / ".claude-plugin").mkdir(parents=True)
        core.write_json(
            source / ".claude-plugin/plugin.json",
            {
                "name": "parent-context",
                "version": "1.0.0",
                "experimental": {"evals": "custom-evals"},
            },
        )
        target = source / "skills/observatory-greeting"
        target.mkdir(parents=True)
        target.joinpath("SKILL.md").write_text(
            (FIXTURES / "observatory-greeting/SKILL.md").read_text()
        )
        (source / "scripts").mkdir()
        (source / "scripts/helper.txt").write_text("PARENT_CONTEXT_PRESERVED")
        (source / "custom-evals").mkdir()
        (source / "custom-evals/should-not-run.md").write_text("sentinel")
        analysis = discover(str(target))
        stage = adapters.native_stage(
            analysis, self.case, self.root / "case", {"timeout": 120}
        )
        self.assertEqual(
            (stage / "scripts/helper.txt").read_text(), "PARENT_CONTEXT_PRESERVED"
        )
        self.assertTrue((stage / "skill-evaluator-cases/TC-001/case.yaml").exists())
        self.assertEqual(
            core.read_data(stage / ".claude-plugin/plugin.json")["name"],
            "parent-context",
        )

    def test_actual_artifact_deleted_or_modified_rejected(self):
        d = self.root / "cases/TC-001/artifacts"
        d.mkdir()
        p = d / "answer.md"
        p.write_text("real output")
        e = copy.deepcopy(self.execution)
        e["artifacts"]["files"] = [
            {
                "path": "answer.md",
                "exists": True,
                "sha256": core.hash_bytes(p.read_bytes()),
            }
        ]
        core.validate_artifact_files(self.root, "TC-001", e)
        p.write_text("changed")
        with self.assertRaises(core.EvalError):
            core.validate_artifact_files(self.root, "TC-001", e)
        p.unlink()
        with self.assertRaises(core.EvalError):
            core.validate_artifact_files(self.root, "TC-001", e)

    def test_evidence_hashes_reject_deleted_or_changed_output(self):
        d = self.root / "cases/TC-001"
        (d / "conversation.txt").write_text("trace")
        core.write_json(d / "artifacts.json", {"files": []})
        core.write_json(d / "execution.json", self.execution)
        core.write_json(d / "prompt.json", {"prompt": "test"})
        values = core.evidence_hashes(self.root, "TC-001")
        core.verify_evidence_hashes(self.root, values)
        (d / "response.txt").write_text("fabricated")
        with self.assertRaises(core.EvalError):
            core.verify_evidence_hashes(self.root, values)
        (d / "response.txt").unlink()
        with self.assertRaises(core.EvalError):
            core.verify_evidence_hashes(self.root, values)

    def test_derived_likert_dimensions_are_recomputed_from_votes(self):
        j = self.judgment()
        j["dimensions"]["best_practices"].update(score=4.83, rubric_level=5)
        j["dimensions"]["business_impact"].update(score=2.6, rubric_level=3)
        core.validate_judgment(j, {**self.case, "_mode": "basic"}, False, self.root)
        graded = core.grade_case(self.case, self.execution, [j] * 3, False, "basic")
        self.assertEqual(graded["dimensions"]["best_practices"], 5)
        self.assertEqual(graded["dimensions"]["business_impact"], 5)

    def test_mock_hook_blocks_unknown_and_quotes_canned_data(self):
        from mock_hook import decision

        cfg = {
            "patterns": ["meta status"],
            "mock_data": {
                "meta status": {"stdout": "$(touch SHOULD_NOT_EXIST)", "exit_code": 0}
            },
        }
        out = decision({"tool_input": {"command": "meta status"}}, cfg)[
            "hookSpecificOutput"
        ]
        self.assertEqual(out["permissionDecision"], "allow")
        result = subprocess.run(
            ["sh", "-c", out["updatedInput"]["command"]],
            cwd=self.root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout, "$(touch SHOULD_NOT_EXIST)")
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())
        self.assertEqual(
            decision({"tool_input": {"command": "curl live"}}, cfg)[
                "hookSpecificOutput"
            ]["permissionDecision"],
            "deny",
        )

    def test_publication_bridge_mock_is_explicit_and_idempotent(self):
        bridge = self.root / "bridge.py"
        counter = self.root / "count"
        bridge.write_text(
            "import json,sys\nfrom pathlib import Path\nr=json.load(sys.stdin)\np=Path("
            + repr(str(counter))
            + ')\np.write_text(str(int(p.read_text())+1) if p.exists() else "1")\nprint(json.dumps({"status":"ok","idempotency_key":r["idempotency_key"],"url":"https://example.invalid/mock"}))\n'
        )
        config = {
            "skillwatch": {
                "command": [sys.executable, str(bridge)],
                "contract_provenance": "deterministic fixture, not real SkillWatch",
            }
        }
        summary = {"run_id": "fixture"}
        publish(self.root, summary, config, "skillwatch")
        publish(self.root, summary, config, "skillwatch")
        self.assertEqual(counter.read_text(), "1")

    def test_binary_report_uses_pass_rates_and_verdicts(self):
        case = core.read_data(FIXTURES / "basic-binary.yaml")["test_cases"][0]
        e = copy.deepcopy(self.execution)
        evaluate.persist_execution(self.root, case, e)
        graded = core.grade_case(case, e, [self.judgment(True)] * 3, True, "basic")
        graded["judge_cost_usd"] = 0
        core.write_json(self.root / "evaluations/TC-001.json", graded)
        manifest = {
            "run_id": "binary-fixture",
            "options": {"mode": "basic", "binary": True},
            "skill": {"name": "observatory-greeting", "description": "Test fixture"},
            "analysis": {"purpose": "Binary report test"},
            "cases": {
                "TC-001": {
                    "evidence_hashes": core.evidence_hashes(self.root, "TC-001", True)
                }
            },
        }
        summary = core.aggregate([graded], manifest)
        write_reports(self.root, summary, manifest)
        page = (self.root / "REPORT.html").read_text()
        self.assertIn("Dimension pass rates", page)
        self.assertIn("PASS", page)
        self.assertNotIn('"grade":', page)
        self.assertNotIn("Composite score:", (self.root / "REPORT.md").read_text())

    def test_resume_rejects_changed_options_and_skill(self):
        import argparse
        import shutil

        source = self.root / "target"
        shutil.copytree(FIXTURES / "observatory-greeting", source)
        analysis = discover(str(source))
        criteria = core.read_data(FIXTURES / "basic.yaml")
        behavior = criteria.pop("analysis")
        opts = {"mode": "basic", "binary": False}
        manifest = {
            "evaluator_version": core.VERSION,
            "options": opts,
            "options_hash": core.digest(opts),
            "analysis": behavior,
            "behavior_hash": core.digest(behavior),
            "evaluator_hash": snapshot_hash(evaluate.ROOT),
            "criteria_hash": core.digest(criteria),
            "config": {},
            "config_hash": core.digest({}),
            "skill": analysis,
        }
        core.write_json(self.root / "manifest.json", manifest)
        core.write_json(self.root / "criteria.yaml", criteria)
        core.write_json(self.root / "analysis.json", analysis)
        args = argparse.Namespace(resume=str(self.root))
        evaluate.resume(args)
        manifest["options"]["binary"] = True
        core.write_json(self.root / "manifest.json", manifest)
        with self.assertRaises(core.EvalError):
            evaluate.resume(args)
        manifest["options"]["binary"] = False
        core.write_json(self.root / "manifest.json", manifest)
        (source / "SKILL.md").write_text("changed")
        with self.assertRaises(core.EvalError):
            evaluate.resume(args)

    def test_author_repairs_mixed_scales_once_without_executing(self):
        from unittest.mock import patch

        criteria = core.read_data(FIXTURES / "basic.yaml")
        behavior = criteria.pop("analysis")
        broken = copy.deepcopy(criteria)
        broken["test_cases"][0]["quality_criteria"]["semantic_checks"][0]["rubric"] = {
            "0": "fail",
            "1": "pass",
        }
        analysis = discover(str(FIXTURES / "observatory-greeting"))
        opts = {
            "mode": "basic",
            "binary": False,
            "judge_model": None,
            "judge_timeout": 10,
        }
        sequence = [
            ({"analysis": behavior, "criteria": broken}, {"cost_usd": 0.2}),
            ({"analysis": behavior, "criteria": criteria}, {"cost_usd": 0.1}),
        ]
        with patch.object(evaluate, "agent_json", side_effect=sequence) as agent:
            _, fixed, usage = evaluate.author(analysis, opts, self.root / "author")
        self.assertEqual(agent.call_count, 2)
        self.assertEqual(len(fixed["test_cases"]), 4)
        self.assertAlmostEqual(usage["cost_usd"], 0.3)

    def test_binary_basic_and_thorough_edge_thresholds(self):
        case = core.read_data(FIXTURES / "basic-binary.yaml")["test_cases"][0]
        j = self.judgment(True)
        j["dimensions"]["efficiency"]["score"] = 0
        self.assertEqual(
            core.grade_case(case, self.execution, [j] * 3, True, "basic")["verdict"],
            "PASS",
        )
        j["dimensions"]["invocation"]["score"] = 0
        self.assertEqual(
            core.grade_case(case, self.execution, [j] * 3, True, "basic")["verdict"],
            "FAIL",
        )
        j["dimensions"]["invocation"]["score"] = 1
        j["dimensions"]["task_completion"] = copy.deepcopy(
            j["dimensions"]["invocation"]
        )
        self.assertEqual(
            core.grade_case(case, self.execution, [j] * 3, True, "thorough")["verdict"],
            "PASS",
        )
        j["dimensions"]["task_completion"]["score"] = 0
        self.assertEqual(
            core.grade_case(case, self.execution, [j] * 3, True, "thorough")["verdict"],
            "FAIL",
        )


if __name__ == "__main__":
    unittest.main()
