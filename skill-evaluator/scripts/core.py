"""Portable contracts, validation, evidence checking and scoring. No agent or network calls."""

from __future__ import annotations

import collections
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

VERSION = "1.0.0"
SCHEMA = "skill-evaluator/1"
DIMENSIONS = (
    "invocation",
    "efficiency",
    "best_practices",
    "business_impact",
    "task_completion",
)
BP = (
    "context_management",
    "subagent_architecture",
    "tool_selection",
    "skill_design",
    "process_adherence",
    "error_handling_safety",
)
BI = (
    "time_saved",
    "scale_potential",
    "quality_ceiling",
    "problem_difficulty",
    "productivity_revenue_link",
)
WEIGHTS = dict(zip(DIMENSIONS, (0.10, 0.10, 0.15, 0.15, 0.50)))
DISTRIBUTIONS = {
    "basic": (1, 1, 1, 1, 0),
    "thorough": (2, 1, 2, 2, 3),
    "deep": (7, 4, 7, 5, 7),
}


class EvalError(Exception):
    """Actionable configuration, provenance or infrastructure failure."""


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return hash_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_data(path):
    try:
        with Path(path).open() as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise EvalError(f"{path} 파일을 읽을 수 없습니다: {exc}") from exc


def backup_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_name(
            path.name
            + ".backup-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        # Exclusive creation: concurrent preparation must never destroy old criteria.
        with backup.open("xb") as stream:
            stream.write(path.read_bytes())
    write_json(path, data)  # JSON is a YAML 1.2 subset; preserves exact prompt strings.
    return str(backup) if backup else None


def safe_relative(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise EvalError(f"상위 디렉터리 이동이 없는 상대 경로가 필요합니다: {value}")
    return path


def portable_directory(value):
    if not isinstance(value, str) or not value:
        raise EvalError("working_directory는 비어 있지 않은 문자열이어야 합니다")
    if value.startswith(("/Users/", "/home/")):
        raise EvalError(
            "working_directory에는 ~/ 또는 저장소 상대 경로를 사용하세요. 개인 홈의 절대 경로는 사용할 수 없습니다"
        )
    return value


def validate_criteria(data, mode, binary):
    if not isinstance(data, dict) or not isinstance(data.get("test_cases"), list):
        raise EvalError("평가 기준 최상위에 test_cases 목록이 필요합니다")
    portable_directory(data.get("default_working_directory", "."))
    cases = data["test_cases"]
    ids = set()
    if len(cases) != sum(DISTRIBUTIONS[mode]):
        raise EvalError(
            f"{mode} 모드에는 정확히 {sum(DISTRIBUTIONS[mode])}개 사례가 필요합니다"
        )
    for case in cases:
        for field in (
            "id",
            "name",
            "category",
            "project",
            "target_skills",
            "prompt",
            "description",
            "expected_behavior",
            "eval_target",
            "quality_criteria",
        ):
            if field not in case:
                raise EvalError(f"사례에 {field} 필드가 없습니다")
        cid = case["id"]
        if not re.fullmatch(r"TC-\d{3}", cid) or cid in ids:
            raise EvalError(f"잘못되었거나 중복된 사례 ID: {cid}")
        ids.add(cid)
        if case["category"] not in DIMENSIONS:
            raise EvalError(f"{cid}: category 값이 올바르지 않습니다")
        if not isinstance(case["prompt"], str) or not case["prompt"].strip():
            raise EvalError(f"{cid}: prompt가 비어 있습니다")
        if case["category"] == "invocation" and (
            case.get("forced_context") or re.search(r"(^|\s)/[\w:-]+", case["prompt"])
        ):
            raise EvalError(
                f"{cid}: invocation은 자연어 라우팅으로 확인해야 하며 슬래시 호출이나 강제 맥락 주입은 사용할 수 없습니다"
            )
        if not isinstance(case["target_skills"], list) or not case["target_skills"]:
            raise EvalError(f"{cid}: target_skills가 필요합니다")
        for target in case["target_skills"]:
            safe_relative(target)
        if case["eval_target"] not in ("response", "artifact", "tool_usage", "all"):
            raise EvalError(f"{cid}: eval_target 값이 올바르지 않습니다")
        portable_directory(case.get("working_directory", "."))
        qc = case["quality_criteria"]
        if not isinstance(qc, dict):
            raise EvalError(f"{cid}: quality_criteria는 객체여야 합니다")
        for key in (
            "required_present",
            "required_absent",
            "semantic_checks",
            "artifact_checks",
        ):
            if not isinstance(qc.get(key), list):
                raise EvalError(f"{cid}: {key}는 목록이어야 합니다")
        if not qc["semantic_checks"]:
            raise EvalError(f"{cid}: semantic_checks에 최소 한 개의 검사가 필요합니다")
        for check in qc["semantic_checks"]:
            if (
                not isinstance(check.get("question"), str)
                or not check["question"].strip()
            ):
                raise EvalError(f"{cid}: question이 필요합니다")
            if (
                not isinstance(check.get("weight"), (int, float))
                or isinstance(check["weight"], bool)
                or not math.isfinite(check["weight"])
                or check["weight"] <= 0
            ):
                raise EvalError(f"{cid}: weight는 유한한 양수여야 합니다")
            if {str(k) for k in check.get("rubric", {})} != (
                {"0", "1"} if binary else {"1", "2", "3", "4", "5"}
            ):
                raise EvalError(
                    f"{cid}: rubric에는 선택한 척도의 키만 빠짐없이 있어야 합니다"
                )
        for check in qc["artifact_checks"]:
            safe_relative(check["path"])
        patterns = case.get("intercept_patterns", [])
        tools = case.get("intercept_mcp_tools", [])
        if (patterns or tools) and not case.get("mock_data"):
            raise EvalError(f"{cid}: 호출을 가로채려면 mock_data가 필요합니다")
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise EvalError(f"{cid}: Bash 패턴이 잘못되었습니다: {exc}") from exc
        for name in tools:
            if not re.fullmatch(r"mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_-]+", name):
                raise EvalError(
                    f"{cid}: 실제 런타임의 정확한 MCP 도구 이름이 필요합니다"
                )
            entry = case["mock_data"].get(name, {})
            if not entry.get("runtime_name_verified") or not entry.get("input_schema"):
                raise EvalError(
                    f"{cid}: MCP 모킹에는 확인된 런타임 이름과 tools/list의 input_schema가 필요합니다"
                )
        timeout = case.get("timeout_seconds", 300)
        if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
            raise EvalError(f"{cid}: timeout_seconds는 1~3600이어야 합니다")
    counts = collections.Counter(c["category"] for c in cases)
    if tuple(counts[d] for d in DIMENSIONS) != DISTRIBUTIONS[mode]:
        raise EvalError(
            f"{mode} 범주별 사례 수는 {dict(zip(DIMENSIONS, DISTRIBUTIONS[mode]))}이어야 합니다"
        )
    return data


def normalize_execution(raw, adapter):
    """Both adapters cross this required contract; no guessed MSL field mapping."""
    required = ("conversation", "metadata", "artifacts")
    if any(key not in raw for key in required):
        raise EvalError("어댑터는 conversation, metadata, artifacts를 반환해야 합니다")
    if not isinstance(raw["conversation"], str):
        raise EvalError("conversation은 문자열이어야 합니다")
    md = raw["metadata"]
    for key in (
        "model",
        "started_at",
        "finished_at",
        "duration_seconds",
        "exit_state",
        "timed_out",
        "usage",
        "cost_usd",
        "cost_basis",
    ):
        if key not in md:
            raise EvalError(f"어댑터 metadata에 {key}가 없습니다")
    if not isinstance(md["usage"], dict):
        raise EvalError("usage는 객체여야 하며 확인할 수 없는 수치는 null이어야 합니다")
    if md["cost_usd"] is not None and (
        not isinstance(md["cost_usd"], (int, float)) or md["cost_usd"] < 0
    ):
        raise EvalError("비용 값이 올바르지 않습니다")
    return {
        "schema_version": SCHEMA,
        "conversation": raw["conversation"],
        "metadata": {**md, "adapter": adapter},
        "artifacts": raw["artifacts"],
        "response": raw.get("response", ""),
        "tool_calls": raw.get("tool_calls", []),
    }


def verify_citation(citation, run_dir):
    """Reject fabricated excerpts, wrong line ranges and path escapes."""
    if not isinstance(citation, dict):
        raise EvalError("근거는 객체여야 합니다")
    path = Path(run_dir) / safe_relative(citation.get("path", ""))
    root = Path(run_dir).resolve()
    if not path.resolve().is_relative_to(root):
        raise EvalError("근거 경로가 실행 디렉터리를 벗어납니다")
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeError) as exc:
        raise EvalError(f"근거 파일을 읽을 수 없습니다: {path}") from exc
    start, end = citation.get("line_start"), citation.get("line_end")
    if (
        type(start) is not int
        or type(end) is not int
        or not (1 <= start <= end <= len(lines))
    ):
        raise EvalError("근거의 줄 범위가 파일 범위를 벗어납니다")
    quote = citation.get("quote")
    if (
        not isinstance(quote, str)
        or not quote.strip()
        or quote not in "\n".join(lines[start - 1 : end])
    ):
        raise EvalError("인용한 줄에 해당 인용문이 없습니다")
    return citation


def _score_item(item, binary, run_dir, case, derived=False):
    allowed = (0, 1) if binary else (1, 2, 3, 4, 5)
    if derived and not binary:
        if (
            type(item.get("score")) not in (int, float)
            or not math.isfinite(item["score"])
            or not 1 <= item["score"] <= 5
        ):
            raise EvalError("계산된 차원 점수가 척도 범위를 벗어납니다")
        if (
            item.get("rubric_level") not in allowed
            and item.get("rubric_level") != item["score"]
        ):
            raise EvalError("계산된 rubric_level이 올바르지 않습니다")
    else:
        if type(item.get("score")) not in (int, float) or item["score"] not in allowed:
            raise EvalError("채점 점수가 선택한 척도 범위를 벗어납니다")
        if item.get("rubric_level") != item["score"]:
            raise EvalError("선택한 rubric_level과 score가 같아야 합니다")
    if not item.get("evidence"):
        raise EvalError("모든 점수에는 근거가 필요합니다")
    prefix = f"cases/{case['id']}/"
    target = case["eval_target"]
    allowed = {"metadata.json"}
    if target in ("response", "all"):
        allowed.add("response.txt")
    if target in ("tool_usage", "all") or case["category"] == "invocation":
        allowed.add("tool_calls.json")
    for citation in item["evidence"]:
        path = citation.get("path", "")
        rel = path[len(prefix) :] if path.startswith(prefix) else ""
        artifact = target in ("artifact", "all") and rel.startswith("artifacts/")
        if rel not in allowed and not artifact:
            raise EvalError(
                "해당 사례의 출력을 인용해야 합니다. 사용자 프롬프트, 스킬 지침, 다른 사례는 근거가 될 수 없습니다"
            )
        verify_citation(citation, run_dir)


def validate_judgment(judgment, case, binary, run_dir):
    if judgment.get("case_id") != case["id"]:
        raise EvalError("채점 결과의 case_id가 일치하지 않습니다")
    dims = DIMENSIONS if case.get("_mode") != "basic" else DIMENSIONS[:4]
    if set(judgment.get("dimensions", {})) != set(dims):
        raise EvalError("채점자는 선택된 모든 차원을 채점해야 합니다")
    for dimension, item in judgment["dimensions"].items():
        _score_item(
            item,
            binary,
            run_dir,
            case,
            dimension in ("best_practices", "business_impact"),
        )
    for field, names in (
        ("best_practice_subcriteria", BP),
        ("business_impact_subcriteria", BI),
    ):
        if set(judgment.get(field, {})) != set(names):
            raise EvalError(f"채점 결과에 {field}가 없습니다")
        for item in judgment[field].values():
            _score_item(item, binary, run_dir, case)
    checks = judgment.get("semantic_checks", [])
    if len(checks) != len(case["quality_criteria"]["semantic_checks"]):
        raise EvalError("semantic_checks 개수가 채점 결과와 일치하지 않습니다")
    for index, item in enumerate(checks):
        if item.get("index") != index:
            raise EvalError("semantic_checks의 index가 일치하지 않습니다")
        _score_item(item, binary, run_dir, case)
    return judgment


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def letter(score):
    return (
        "A"
        if score >= 4.5
        else "B"
        if score >= 3.5
        else "C"
        if score >= 3
        else "D"
        if score >= 2
        else "F"
    )


def deterministic_checks(case, execution):
    qc = case["quality_criteria"]
    target = case["eval_target"]
    texts = []
    if target in ("response", "all"):
        texts.append(execution.get("response", ""))
    if target in ("tool_usage", "all"):
        texts.append(json.dumps(execution.get("tool_calls", [])))
    if target in ("artifact", "all"):
        texts.extend(
            a.get("content", "")
            for a in execution["artifacts"].get("files", [])
            if a.get("exists")
        )
    text = "\n".join(texts)
    hits = [s for s in qc["required_present"] if s in text]
    misses = [s for s in qc["required_present"] if s not in text]
    forbidden = [s for s in qc["required_absent"] if s in text]
    # Only response/tool evidence, never the echoed user prompt, participates in textual checks.
    files = {a["path"]: a for a in execution["artifacts"].get("files", [])}
    artifact_failures = []
    for check in qc["artifact_checks"]:
        obj = files.get(check["path"])
        if not obj or not obj.get("exists"):
            artifact_failures.append(check["path"])
    invocations = execution["metadata"].get("skill_invocations", [])
    routing_failure = False
    if case["category"] == "invocation":
        expected = case.get("expect_invocation", True)
        target = case["project"]
        fired = any(s.split(":")[-1] == target for s in invocations)
        routing_failure = fired != expected
    return {
        "required_present_hits": hits,
        "required_present_misses": misses,
        "forbidden_hits": forbidden,
        "missing_artifacts": artifact_failures,
        "routing_failure": routing_failure,
    }


def grade_case(case, execution, judgments, binary, mode):
    checks = deterministic_checks(case, execution)
    fail = any(
        checks[k]
        for k in (
            "required_present_misses",
            "forbidden_hits",
            "missing_artifacts",
            "routing_failure",
        )
    )
    dims = DIMENSIONS[:4] if mode == "basic" else DIMENSIONS

    # Three independent judgments of the same execution; binary majority, Likert median.
    def vote(items):
        vals = sorted(i["score"] for i in items)
        return vals[len(vals) // 2]

    dimension_scores = {d: vote(j["dimensions"][d] for j in judgments) for d in dims}
    bp = {d: vote(j["best_practice_subcriteria"][d] for j in judgments) for d in BP}
    bi = {d: vote(j["business_impact_subcriteria"][d] for j in judgments) for d in BI}
    dimension_scores["best_practices"] = (
        int(sum(bp.values()) >= 4) if binary else mean(bp.values())
    )
    dimension_scores["business_impact"] = (
        int(sum(bi.values()) >= 3) if binary else mean(bi.values())
    )
    sem = []
    for idx, spec in enumerate(case["quality_criteria"]["semantic_checks"]):
        val = vote(j["semantic_checks"][idx] for j in judgments)
        sem.append({"index": idx, "score": val, "weight": spec["weight"]})
        if spec.get("critical", False) and val < (1 if binary else 3):
            fail = True
    semantic = sum(s["score"] * s["weight"] for s in sem) / sum(
        s["weight"] for s in sem
    )
    if binary:
        score = sum(dimension_scores.values()) / len(dims)
        passed = sum(dimension_scores.values()) >= (3 if mode == "basic" else 4)
    else:
        score = (
            mean(dimension_scores.values())
            if mode == "basic"
            else sum(dimension_scores[d] * WEIGHTS[d] for d in dims)
        )
        passed = score >= 3
    return {
        "schema_version": SCHEMA,
        "case_id": case["id"],
        "name": case["name"],
        "category": case["category"],
        "grading": "binary" if binary else "likert",
        "status": "graded",
        "score": score,
        "verdict": "PASS" if passed and not fail else "FAIL",
        **({} if binary else {"grade": letter(score)}),
        "critical_failure": fail,
        "dimensions": dimension_scores,
        **(
            {
                "dimension_verdicts": {
                    d: "PASS" if v else "FAIL" for d, v in dimension_scores.items()
                }
            }
            if binary
            else {}
        ),
        "best_practice_subcriteria": bp,
        "business_impact_subcriteria": bi,
        "semantic_score": semantic,
        "semantic_checks": sem,
        "checks": checks,
        "judge_rounds": judgments,
        "metadata": execution["metadata"],
        "evidence": {
            "transcript": f"cases/{case['id']}/conversation.txt",
            "artifacts": f"cases/{case['id']}/artifacts.json",
        },
    }


def error_case(case, reason, metadata=None):
    return {
        "schema_version": SCHEMA,
        "case_id": case["id"],
        "name": case["name"],
        "category": case["category"],
        "status": "error",
        "verdict": "ERROR",
        "score": None,
        "error": reason,
        "metadata": metadata or {},
        "evidence": {"transcript": f"cases/{case['id']}/conversation.txt"},
    }


def aggregate(results, manifest):
    graded = [r for r in results if r["status"] == "graded"]
    passed = sum(r["verdict"] == "PASS" for r in results)
    binary = manifest["options"]["binary"]
    mode = manifest["options"]["mode"]
    costs = [r["metadata"].get("cost_usd") for r in results]
    judge_costs = [r.get("judge_cost_usd") for r in results]

    def total_known(values):
        return sum(values) if values and all(v is not None for v in values) else None

    dims = DIMENSIONS[:4] if mode == "basic" else DIMENSIONS
    scores = [r["score"] for r in graded]
    score = mean(scores)
    summary = {
        "schema_version": SCHEMA,
        "run_id": manifest["run_id"],
        "mode": mode,
        "grading": "binary" if binary else "likert",
        "total": len(results),
        "passed": passed,
        "failed": sum(r["verdict"] == "FAIL" for r in results),
        "errors": sum(r["status"] == "error" for r in results),
        "pass_rate": passed / len(results) if results else None,
        "score": score,
        "verdict": "PASS" if results and passed == len(results) else "FAIL",
        "categories": {
            d: {
                "count": sum(r["category"] == d for r in results),
                "pass_rate": mean(
                    int(r["verdict"] == "PASS") for r in results if r["category"] == d
                ),
            }
            for d in dims
        },
        "dimensions": {d: mean(r["dimensions"][d] for r in graded) for d in dims},
        "best_practice_subcriteria": {
            d: mean(r["best_practice_subcriteria"][d] for r in graded) for d in BP
        },
        "duration_seconds": sum(
            r["metadata"].get("duration_seconds", 0) or 0 for r in results
        ),
        "execution_cost_usd": total_known(costs),
        "judge_cost_usd": total_known(judge_costs),
        "cost_usd": total_known(costs + judge_costs),
        "known_cost_subtotal_usd": sum(c for c in costs + judge_costs if c is not None),
        "tokens": {
            k: total_known([r["metadata"].get("usage", {}).get(k) for r in results])
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        },
        "recommendations": [
            {
                "case_id": r["case_id"],
                "action": r.get("error")
                or "스킬을 바꾸기 전에 실패한 검사와 인용된 루브릭 차이를 확인하세요.",
            }
            for r in results
            if r["verdict"] != "PASS"
        ],
        "score_distribution": dict(
            collections.Counter(str(r["score"]) for r in graded)
        ),
        "failure_clusters": dict(
            collections.Counter(
                r.get(
                    "error",
                    "critical requirement"
                    if r.get("critical_failure")
                    else "rubric threshold",
                )
                for r in results
                if r["verdict"] != "PASS"
            )
        ),
        "results": results,
    }
    if not binary and score is not None:
        summary["grade"] = letter(score)
    return summary


def evidence_hashes(run_dir, case_id, include_evaluation=False):
    root = Path(run_dir)
    d = root / "cases" / case_id
    paths = [
        d / name
        for name in (
            "conversation.txt",
            "response.txt",
            "metadata.json",
            "artifacts.json",
            "tool_calls.json",
            "execution.json",
            "prompt.json",
        )
    ]
    if (d / "trace.jsonl").exists():
        paths.append(d / "trace.jsonl")
    if (d / "artifacts").exists():
        paths.extend(p for p in (d / "artifacts").rglob("*") if p.is_file())
    if include_evaluation:
        paths.append(root / "evaluations" / f"{case_id}.json")
    values = {}
    for p in paths:
        if p.is_symlink() or not p.is_file():
            raise EvalError(f"실행 근거가 없거나 안전하지 않은 경로입니다: {p}")
        values[str(p.relative_to(root))] = hash_bytes(p.read_bytes())
    return values


def verify_evidence_hashes(run_dir, values):
    if not values:
        raise EvalError("근거 해시가 없어 점수를 재사용할 수 없습니다")
    for rel, expected in values.items():
        p = Path(run_dir) / safe_relative(rel)
        if p.is_symlink() or not p.is_file() or hash_bytes(p.read_bytes()) != expected:
            raise EvalError(
                f"실행 근거가 바뀌었거나 없습니다: {rel}; 새 실행을 만드세요"
            )


def validate_artifact_files(run_dir, case_id, execution):
    root = Path(run_dir).resolve()
    for artifact in execution["artifacts"].get("files", []):
        if not artifact.get("exists"):
            continue
        rel = Path("cases") / case_id / "artifacts" / safe_relative(artifact["path"])
        p = root / rel
        if p.is_symlink() or not p.resolve().is_relative_to(root) or not p.is_file():
            raise EvalError(f"실제 산출물 파일이 없습니다: {rel}")
        if hash_bytes(p.read_bytes()) != artifact.get("sha256"):
            raise EvalError(f"산출물 해시가 일치하지 않습니다: {rel}")
