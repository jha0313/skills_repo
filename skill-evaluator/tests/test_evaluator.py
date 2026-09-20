import copy
import json
import signal
import subprocess
import sys
import tempfile
import time
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
