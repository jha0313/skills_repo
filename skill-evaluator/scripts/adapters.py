"""Native Claude evaluation (claude plugin eval) and independent judge sessions."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from core import (
    EvalError,
    hash_bytes,
    normalize_execution,
    now,
    write_json,
)
from discovery import copy_tree

_ACTIVE: set[subprocess.Popen] = set()
_ACTIVE_LOCK = threading.Lock()
_CANCEL = threading.Event()


def cancel_processes():
    _CANCEL.set()
    with _ACTIVE_LOCK:
        for proc in list(_ACTIVE):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def reset_cancellation():
    _CANCEL.clear()


def run_process(argv, cwd, timeout, log_prefix, input_text=None, env=None):
    """Bound the whole process group; retain stdout/stderr even on interruption."""
    if _CANCEL.is_set():
        raise EvalError("실행이 중단되어 대기 중인 프로세스를 취소했습니다")
    prefix = Path(log_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )
    with _ACTIVE_LOCK:
        _ACTIVE.add(proc)
        if _CANCEL.is_set():
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    timed_out = False
    try:
        out, err = proc.communicate(input_text, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        timed_out = isinstance(exc, subprocess.TimeoutExpired)
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
        prefix.with_suffix(".stdout").write_text(out)
        prefix.with_suffix(".stderr").write_text(err)
        if not timed_out:
            raise
    with _ACTIVE_LOCK:
        _ACTIVE.discard(proc)
    prefix.with_suffix(".stdout").write_text(out)
    prefix.with_suffix(".stderr").write_text(err)
    if _CANCEL.is_set():
        raise EvalError("실행이 중단되어 진행 중인 프로세스를 취소했습니다")
    return {
        "stdout": out,
        "stderr": err,
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "duration_seconds": time.monotonic() - started,
    }


def check_dependencies(run_dir=None):
    if not shutil.which("claude"):
        raise EvalError(
            "Claude Code CLI가 없습니다. 설치: https://code.claude.com/docs/en/setup ; 설치 후 claude auth login을 실행하세요"
        )
    help_result = subprocess.run(
        ["claude", "plugin", "eval", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    required = ("--no-publish", "--keep-temp", "--ablation", "--output-dir", "--mocks")
    if help_result.returncode or any(v not in help_result.stdout for v in required):
        raise EvalError(
            "현재 Claude CLI에 필요한 native eval 기능이 없습니다. claude update 후 claude plugin eval --help를 확인하세요"
        )
    version = subprocess.run(
        ["claude", "--version"], capture_output=True, text=True, timeout=30
    ).stdout.strip()
    if run_dir:
        Path(run_dir, "cli-eval-help.txt").write_text(help_result.stdout)
    return {
        "claude_version": version,
        "discovery_helper": "bundled discovery.py + claude plugin list --json",
        "visualization_helper": "bundled reporting.py (no external publication)",
        "native_eval": True,
    }


def native_stage(analysis, case, case_dir, options):
    stage = Path(case_dir) / "native-plugin"
    stage.mkdir(parents=True, exist_ok=True)
    name = analysis["name"]
    if analysis.get("plugin_root"):
        copy_tree(analysis["plugin_root"], stage)
    else:
        write_json(
            stage / ".claude-plugin/plugin.json",
            {
                "name": "evaluated-skill",
                "version": "1.0.0",
                "description": "스킬 평가를 위한 격리된 소스 스냅샷",
            },
        )
        copy_tree(analysis["installed_path"], stage / "skills" / name)
    casepath = stage / "skill-evaluator-cases" / case["id"]
    casepath.mkdir(parents=True, exist_ok=True)
    native = {
        "schema_version": "1.0",
        "name": case["id"],
        "description": case["description"],
        "runs": 1,
        "execution": {
            "prompt": case["prompt"],
            "max_turns": case.get("max_turns", 15),
            "timeout_seconds": case.get("timeout_seconds", options["timeout"]),
            "allowed_tools": ["Read", "Glob", "Grep", "Skill"]
            + options.get("allow_tools", []),
            "artifact_publish": False,
        },
        # Native free grader only asserts there is evidence; scoring is our independent judge phase.
        "graders": [
            {
                "name": "nonempty",
                "type": "regex",
                "target": "last_message",
                "pattern": r"\S",
                "match": "contains",
                "weight": 1,
            }
        ],
    }
    if options.get("model"):
        native["execution"]["model"] = options["model"]
    if case["category"] != "invocation" and case.get("forced_context", True):
        native["execution"]["append_system_prompt"] = (
            f"이 동작 평가에서는 {analysis.get('plugin_name', 'evaluated-skill')}:{name} 스킬을 사용하세요. 필요한 참고 문서를 읽으세요."
        )
    wd = case.get("working_directory", options.get("default_working_directory", "."))
    # Blank '.' is an intentional empty sandbox. Explicit directories are copied as data by
    # an evaluator-owned scaffold. No project hooks/git config or user changes execute.
    if wd != ".":
        source = Path(wd).expanduser()
        if not source.is_absolute():
            source = Path(analysis["source_path"]) / source
        if not source.is_dir():
            raise EvalError(f"작업 디렉터리가 없습니다: {wd}")
        copy_tree(source, stage / "fixture")
        for config_path in (stage / "fixture/.claude", stage / "fixture/.mcp.json"):
            if config_path.is_dir():
                shutil.rmtree(config_path)
            elif config_path.exists():
                config_path.unlink()
        # The native runner resolves scaffold_script relative to the case directory.
        scaffold = casepath / "scaffold.sh"
        scaffold.write_text(
            "#!/bin/sh\nset -eu\ncp -R "
            + shlex.quote(str(stage / "fixture"))
            + "/. .\n"
        )
        native["context"] = {"scaffold_script": "scaffold.sh"}
    if case.get("intercept_patterns"):
        hook = stage / "mock-hook.py"
        hook.write_text(Path(__file__).with_name("mock_hook.py").read_text())
        write_json(
            stage / "bash-mocks.json",
            {"patterns": case["intercept_patterns"], "mock_data": case["mock_data"]},
        )
        hooks_path = stage / "hooks/hooks.json"
        hooks = (
            json.loads(hooks_path.read_text()) if hooks_path.exists() else {"hooks": {}}
        )
        hooks.setdefault("hooks", {}).setdefault("PreToolUse", []).insert(
            0,
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": shlex.quote(sys.executable)
                        + " "
                        + shlex.quote(str(hook))
                        + " "
                        + shlex.quote(str(stage / "bash-mocks.json")),
                        "timeout": 5,
                    }
                ],
            },
        )
        write_json(hooks_path, hooks)
        native["execution"]["allowed_tools"].append("Bash")
    mock_schemas = {}
    for runtime in case.get("intercept_mcp_tools", []):
        server, tool = runtime[len("mcp__") :].split("__", 1)
        obj = case["mock_data"][runtime]
        folder = stage / "skill-evaluator-cases/mocks" / server
        folder.mkdir(parents=True, exist_ok=True)
        fm = {"expect": obj.get("expect", {}), "error": obj.get("error", False)}
        import yaml

        (folder / f"{tool}.md").write_text(
            "---\n" + yaml.safe_dump(fm) + "---\n" + json.dumps(obj["response"])
        )
        mock_schemas.setdefault(server, []).append(
            {
                "name": tool,
                "description": obj.get("description", tool),
                "inputSchema": obj["input_schema"],
            }
        )
    for server, schemas in mock_schemas.items():
        write_json(
            stage / "skill-evaluator-cases/mocks" / server / "_tools.json",
            {"tools": schemas},
        )
    write_json(casepath / "case.yaml", native)
    return stage


def parse_trace(text):
    indexed = []
    # JSONL is newline-delimited only; str.splitlines() would also break on U+2028 and
    # similar separators that legitimately appear inside JSON strings.
    for line_no, line in enumerate(text.split("\n"), 1):
        if line.strip():
            try:
                indexed.append((line_no, json.loads(line)))
            except json.JSONDecodeError as exc:
                raise EvalError(
                    "native JSONL 실행 기록의 형식이 잘못되었습니다"
                ) from exc
    events = [event for _, event in indexed]
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    init = next((e for e in events if e.get("subtype") == "init"), {})
    calls = []
    responses = []
    agent_ids = set()
    for line_no, event in indexed:
        if event.get("type") != "assistant":
            continue
        # Actor attribution comes from the native event, never from assistant text:
        # an explicit null parent_tool_use_id is the evaluated session itself, a set
        # value is a delegated worker, and a missing key is unknown.
        if "parent_tool_use_id" not in event:
            actor = "unknown"
        elif event["parent_tool_use_id"] is None:
            actor = "parent"
        else:
            actor = "worker"
        parent = event.get("parent_tool_use_id")
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "tool_use":
                calls.append(
                    {
                        "name": part["name"],
                        "input": part.get("input", {}),
                        "id": part.get("id"),
                        "actor": actor,
                        "parent_tool_use_id": parent,
                        "lineage_verified": (parent in agent_ids)
                        if actor == "worker"
                        else None,
                        "trace_line": line_no,
                    }
                )
                if part["name"] == "Agent" and part.get("id"):
                    agent_ids.add(part["id"])
            elif part.get("type") == "text":
                responses.append(part["text"])
    response = final.get("result") or "\n".join(responses)
    return events, final, init, calls, response


def collect_native_files(trace_path, case_dir):
    """Read preserved native data, never execute it; re-seal the native directory afterward."""
    files = []
    trace = Path(trace_path).resolve()
    sandbox = trace.parent.parent
    if (
        trace.name != "trace.jsonl"
        or trace.parent.name != "out"
        or not sandbox.name.startswith(("e-", "claude-eval-"))
    ):
        raise EvalError(
            "예상과 다른 native sandbox 구조입니다. 산출물을 수집하기 전에 현재 CLI를 확인하세요"
        )
    sealed = sandbox / "sealed"
    if not sealed.is_dir() or sealed.is_symlink():
        return files
    old_mode = sealed.stat().st_mode & 0o777
    try:
        sealed.chmod(0o700)
        cwd = sealed / "home/cwd"
        if not cwd.is_dir() or cwd.is_symlink():
            return files
        for p in sorted(cwd.rglob("*")):
            rel = p.relative_to(cwd)
            if any(
                x in (".git", ".claude", "node_modules", "__pycache__")
                for x in rel.parts
            ):
                continue
            if p.is_symlink():
                files.append(
                    {
                        "path": str(rel),
                        "exists": False,
                        "error": "심볼릭 링크 산출물은 따라가지 않았습니다",
                    }
                )
                continue
            if p.is_file():
                if p.stat().st_size > 20_000_000:
                    raise EvalError(
                        f"산출물이 수집 한도 20MB를 초과합니다: {rel}; 필요한 산출물만 내보내도록 설정하세요"
                    )
                target = Path(case_dir) / "artifacts" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
                files.append(
                    {
                        "path": str(rel),
                        "exists": True,
                        "sha256": hash_bytes(target.read_bytes()),
                        "bytes": target.stat().st_size,
                        "evidence_path": str(
                            Path("cases") / Path(case_dir).name / "artifacts" / rel
                        ),
                        "content": target.read_text(errors="replace"),
                    }
                )
    finally:
        sealed.chmod(old_mode)
    return files


def native_execute(analysis, case, case_dir, options):
    case_dir = Path(case_dir)
    if case.get("intercept_patterns") and not case.get("_mock_probe"):
        marker = "SKILL_EVAL_PROBE_" + uuid.uuid4().hex
        probe = dict(
            case,
            category="task_completion",
            forced_context=False,
            _mock_probe=True,
            prompt="Bash로 정확히 printf skill-evaluator-mock-probe를 실행하고 관찰한 출력을 보고하세요.",
            intercept_patterns=["printf skill-evaluator-mock-probe"],
            intercept_mcp_tools=[],
            mock_data={
                "printf skill-evaluator-mock-probe": {"stdout": marker, "exit_code": 0}
            },
        )
        probe_dir = case_dir / "mock-capability-probe"
        probe_dir.mkdir(parents=True, exist_ok=True)
        native_execute(analysis, probe, probe_dir, {**options, "allow_tools": []})
        proof_events = parse_trace((probe_dir / "trace.jsonl").read_text())[0]
        observed = [
            p.get("content")
            for e in proof_events
            if e.get("type") == "user"
            for p in e.get("message", {}).get("content", [])
            if isinstance(p, dict) and p.get("type") == "tool_result"
        ]
        if not any(marker in str(value) for value in observed):
            raise EvalError(
                "현재 native runner가 Bash mock hook을 적용하지 않아 실제 사례 실행을 거부합니다. mock-capability-probe를 확인하세요."
            )
    stage = native_stage(analysis, case, case_dir, options)
    rawpath = case_dir / "native-result.json"
    argv = [
        "claude",
        "plugin",
        "eval",
        str(stage),
        "--eval-dir",
        "skill-evaluator-cases",
        "--case",
        case["id"],
        "--ablation",
        "none",
        "--runs",
        "1",
        "--concurrency",
        "1",
        "--no-publish",
        "--mocks",
        "record",
        "--keep-temp",
        "--json",
        str(rawpath),
        "--output-dir",
        str(case_dir / "native-results"),
    ]
    if options.get("trust_target"):
        argv.append("--trust-plugin")
    if options.get("model"):
        argv += ["--model", options["model"]]
    if (
        case.get("working_directory", options.get("default_working_directory", "."))
        != "."
    ):
        argv.append("--scaffold")
    grants = options.get("allow_tools", []) + (
        ["Bash"] if case.get("intercept_patterns") else []
    )
    if grants:
        argv += ["--allow-tools", *grants]
    start = now()
    write_json(case_dir / "command.json", {"argv": argv})
    env = dict(os.environ)
    result = run_process(
        argv,
        stage,
        case.get("timeout_seconds", options["timeout"]) + 90,
        case_dir / "runner",
        env=env,
    )
    if not rawpath.exists():
        raise EvalError(
            "native runner가 결과를 만들지 못했습니다: " + result["stderr"][-1200:]
        )
    raw = json.loads(rawpath.read_text())
    plugins = raw.get("suite", {}).get("plugins", [])
    if not plugins or any(
        p.get("problem") in ("manifest_invalid", "disabled_by_default", "will_not_load")
        for p in plugins
    ):
        raise EvalError(
            "native plugin이 로드되지 않았습니다. 잘못된 호출 근거로 인정하지 않습니다"
        )
    if len(raw.get("cases", [])) != 1 or raw["cases"][0].get("name") != case["id"]:
        raise EvalError(
            "native runner가 예상하지 않은 사례를 선택했습니다. 섞인 사례의 점수를 인정하지 않습니다"
        )
    try:
        arm = raw["cases"][0]["arms"]["with"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise EvalError(
            "native 출력 스키마가 바뀌었습니다. native-result.json을 확인하세요"
        ) from exc
    tracepath = arm.get("tracePath", "")
    if not tracepath or not Path(tracepath).is_file():
        raise EvalError(
            "읽을 수 있는 native 실행 기록이 없습니다: " + str(arm.get("error"))
        )
    trace = Path(tracepath).read_text()
    (case_dir / "trace.jsonl").write_text(trace)
    events, final, init, calls, response = parse_trace(trace)
    files = collect_native_files(tracepath, case_dir)
    (case_dir / "response.txt").write_text(response)
    write_json(case_dir / "tool_calls.json", calls)
    write_json(case_dir / "prompt.json", {"prompt": case["prompt"]})
    transcript = "USER PROMPT\n" + case["prompt"] + "\n\nRAW CLAUDE EVENTS\n" + trace
    usage = final.get("usage", {})
    md = {
        "model": init.get("model"),
        "started_at": arm.get("startedAt", start),
        "finished_at": now(),
        "duration_seconds": arm.get("durationSeconds", result["duration_seconds"]),
        "exit_state": "error"
        if arm.get("error") or final.get("is_error")
        else "completed",
        "timed_out": result["timed_out"]
        or any(
            w in str(arm.get("error", "")).lower() for w in ("timeout", "timed out")
        ),
        "usage": {
            k: usage.get(k)
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        },
        "cost_usd": arm.get("costUsd"),
        "cost_basis": "Claude CLI "
        + raw.get("claudeVersion", "unknown")
        + " list-price estimate",
        "skill_invocations": [
            c["input"].get("skill", "") for c in calls if c["name"] == "Skill"
        ],
        "permission_denials": final.get("permission_denials", []),
        "subagent_stats": final.get("subagent_stats"),
        "error": arm.get("error"),
        "mock_status": arm.get("mocks"),
        "mock_unmatched": any(
            "UNMOCKED_EXTERNAL_CALL" in str(p.get("content", ""))
            for e in events
            if e.get("type") == "user"
            for p in e.get("message", {}).get("content", [])
            if isinstance(p, dict) and p.get("type") == "tool_result"
        ),
        "native_sandbox": str(Path(tracepath).parent.parent),
    }
    urls = sorted(set(re.findall(r'https?://[^\s<>"\\]+', trace)))
    artifacts = {
        "files": files,
        "urls": [
            {"url": url, "provenance": "transcript mention; reachability not verified"}
            for url in urls
        ],
    }
    return normalize_execution(
        {
            "conversation": transcript,
            "metadata": md,
            "artifacts": artifacts,
            "response": response,
            "tool_calls": calls,
        },
        "claude-native",
    )


def agent_json(prompt, out_dir, model=None, timeout=300):
    """Separate clean judge/author session. No skills, tools, hooks or MCP execution."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        "claude",
        "-p",
        "--safe-mode",
        "--output-format",
        "json",
        "--tools",
        "",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--setting-sources",
        "",
        "--settings",
        '{"disableAllHooks":true}',
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
    ]
    if model:
        argv += ["--model", model]
    (out_dir / "prompt.txt").write_text(prompt)
    result = run_process(argv, out_dir, timeout, out_dir / "agent", prompt)
    if result["timed_out"] or result["exit_code"]:
        raise EvalError("독립 에이전트 실행에 실패했습니다: " + result["stderr"][-800:])
    try:
        outer = json.loads(result["stdout"])
        answer = outer.get("structured_output") or outer.get("result", "")
        if isinstance(answer, str):
            answer = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", answer.strip()))
    except (ValueError, TypeError) as exc:
        raise EvalError(
            "독립 에이전트가 유효한 JSON을 반환하지 않았습니다. 원시 출력은 보존했습니다"
        ) from exc
    if outer.get("is_error"):
        raise EvalError("독립 에이전트가 실행 환경 오류를 보고했습니다")
    write_json(out_dir / "result.json", answer)
    return answer, {
        "cost_usd": outer.get("total_cost_usd"),
        "usage": outer.get("usage", {}),
        "duration_seconds": result["duration_seconds"],
        "model": model
        or ",".join(outer.get("modelUsage", {}))
        or "CLI configured default",
    }
