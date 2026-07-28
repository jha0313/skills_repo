#!/usr/bin/env python3
"""AI-Readiness Cartography — repo scorer (v2 rubric, 100 points, 7 categories).

Audits a repository against the 7-category AI-Ready rubric and emits structured
findings, ROI-ranked actions, and a JSON scorecard suitable for the dashboard
template at assets/template.html.

Usage:
    python score.py [repo_path]                # default: .
    python score.py /path/to/repo --json out.json
    python score.py . --markdown               # human-readable to stdout (default)

Pure stdlib — no external dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
IGNORE_DIRS = {
    "node_modules", ".venv", "venv", ".git", ".next", "dist", "build",
    "__pycache__", ".turbo", ".ruff_cache", ".pytest_cache", ".mypy_cache",
    "target", "out", "coverage", ".cache", ".idea", ".vscode",
}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".sql", ".swift", ".cs"}
CONTEXT_FILES = ("CLAUDE.md", "AGENTS.md", "README.md")
PRIMARY_CONTEXT = ("CLAUDE.md", "AGENTS.md")  # anything stronger than README

# Heuristic regex
RE_PATH_REF = re.compile(
    r"(?<![A-Za-z0-9_/])"
    r"((?:\./|[A-Za-z0-9_]+/)[A-Za-z0-9_./-]+\.(?:py|ts|tsx|js|jsx|md|sql|json|yaml|yml|toml|html|css|sh|go|rs|java|kt|rb|php))"
)
RE_BASH_FENCE = re.compile(r"```(?:bash|sh|shell|zsh|console)\s*\n([\s\S]*?)```", re.IGNORECASE)
RE_NON_OBVIOUS = re.compile(r"\b(Why:|Note:|Gotcha|Warning|Don't|Caveat|Important:)", re.IGNORECASE)
RE_REL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://)([^)]+)\)")
RE_DEPS_HEADING = re.compile(r"^#+\s.*(depend|cross[- ]module|imports?|see also|related)", re.IGNORECASE | re.MULTILINE)
RE_PURPOSE_HEADING = re.compile(r"^#+\s.*(purpose|owns?|configures?|overview)", re.IGNORECASE | re.MULTILINE)
RE_PATTERN_HEADING = re.compile(r"^#+\s.*(pattern|how to|common change|workflow|recipe)", re.IGNORECASE | re.MULTILINE)
RE_MERMAID = re.compile(r"```mermaid", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------------
@dataclass
class Module:
    path: Path
    rel: str
    code_files: int
    has_context: bool
    context_file: Path | None = None
    context_kind: str = ""  # "CLAUDE.md" | "AGENTS.md" | "README.md" | ""


@dataclass
class CategoryScore:
    name: str
    score: int
    max: int
    evidence: dict[str, Any] = field(default_factory=dict)
    sub_scores: dict[str, int] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)


@dataclass
class Action:
    title: str
    category: str
    effort: str            # S / M / L
    effort_hours: float
    impact: str            # human-readable
    impact_score: int      # 1-10
    priority: float        # impact / effort_hours


@dataclass
class Report:
    meta: dict[str, Any]
    total: int
    grade: str
    grade_color: str
    categories: dict[str, CategoryScore]
    insights: list[str]
    actions: list[Action]
    extras: dict[str, Any]


# ----------------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------------
def walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            out.append(Path(r) / f)
    return out


def find_core_modules(repo: Path) -> list[Module]:
    """Top-level + apps/* + packages/* + services/* code-bearing dirs."""
    candidates: list[Path] = []

    # top-level dirs
    for d in sorted(repo.iterdir()):
        if not d.is_dir():
            continue
        if d.name in IGNORE_DIRS or d.name.startswith("."):
            continue
        candidates.append(d)

    # monorepo level
    for parent_name in ("apps", "packages", "services"):
        parent = repo / parent_name
        if parent.exists() and parent.is_dir():
            # remove the parent from candidates if there
            candidates = [c for c in candidates if c != parent]
            for d in sorted(parent.iterdir()):
                if d.is_dir() and d.name not in IGNORE_DIRS:
                    candidates.append(d)

    modules: list[Module] = []
    for d in candidates:
        code_count = 0
        for r, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in IGNORE_DIRS and not x.startswith(".")]
            for f in files:
                if Path(f).suffix in CODE_EXTS:
                    code_count += 1
        if code_count == 0:
            continue
        ctx_file, ctx_kind = pick_context_file(d)
        modules.append(Module(
            path=d,
            rel=str(d.relative_to(repo)),
            code_files=code_count,
            has_context=ctx_file is not None,
            context_file=ctx_file,
            context_kind=ctx_kind,
        ))
    return modules


def pick_context_file(d: Path) -> tuple[Path | None, str]:
    for name in CONTEXT_FILES:
        p = d / name
        if p.exists():
            return p, name
    return None, ""


def find_all_context_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    for r, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            if f in CONTEXT_FILES:
                out.append(Path(r) / f)
    return out


def find_root_claude(repo: Path) -> Path | None:
    p = repo / "CLAUDE.md"
    return p if p.exists() else None


def count_lines(p: Path) -> int:
    try:
        return len(p.read_text(errors="ignore").splitlines())
    except Exception:
        return 0


def read_text(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""


def file_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except Exception:
        return 0.0


# ----------------------------------------------------------------------------
# A. Navigation Coverage
# ----------------------------------------------------------------------------
def score_a(modules: list[Module], root_claude: Path | None) -> CategoryScore:
    total = max(1, len(modules))
    covered = sum(1 for m in modules if m.has_context)
    coverage = covered / total
    pts = round(coverage * 15)
    if root_claude is None:
        pts = max(0, pts - 2)
    pts = max(0, min(15, pts))

    findings: list[str] = []
    if coverage < 1.0:
        gap_modules = [m.rel for m in modules if not m.has_context]
        findings.append(f"{len(gap_modules)} core modules without context: {', '.join(gap_modules[:6])}")
    if root_claude is None:
        findings.append("root CLAUDE.md missing — no entry-point briefing")

    return CategoryScore(
        name="AI Navigation & Coverage",
        score=pts,
        max=15,
        evidence={
            "core_modules": total,
            "covered_modules": covered,
            "coverage_ratio": round(coverage, 3),
            "root_claude": str(root_claude.name) if root_claude else None,
        },
        findings=findings,
    )


# ----------------------------------------------------------------------------
# B. Context Document Quality
# ----------------------------------------------------------------------------
def score_b(context_files: list[Path], repo: Path) -> CategoryScore:
    if not context_files:
        return CategoryScore(name="Context Document Quality", score=0, max=20,
                             evidence={"context_files": 0},
                             findings=["no context files at all"])

    n = len(context_files)
    sub: dict[str, int] = {}

    # B1 Conciseness — 25-35 lines target. Score = 4 * fraction within sane band.
    line_counts = [count_lines(p) for p in context_files]
    concise = sum(1 for ln in line_counts if 10 <= ln <= 80) / n
    sub["B1_Conciseness"] = round(4 * concise)
    over_long = [(p, ln) for p, ln in zip(context_files, line_counts) if ln > 100]

    # B2 Quick Commands — bash fence presence
    quick = sum(1 for p in context_files if RE_BASH_FENCE.search(read_text(p))) / n
    sub["B2_QuickCommands"] = round(4 * quick)

    # B3 Key Files — 3-5 path refs ideal
    key_ratio = 0.0
    for p in context_files:
        text = read_text(p)
        refs = RE_PATH_REF.findall(text)
        uniq = len(set(refs))
        if uniq >= 3:
            key_ratio += 1
        elif uniq >= 1:
            key_ratio += 0.5
    sub["B3_KeyFiles"] = round(4 * key_ratio / n)

    # B4 Non-Obvious patterns
    nonobvious = sum(1 for p in context_files if RE_NON_OBVIOUS.search(read_text(p))) / n
    sub["B4_NonObvious"] = round(4 * nonobvious)

    # B5 See Also / cross refs
    crossref = sum(1 for p in context_files if RE_REL_LINK.search(read_text(p))) / n
    sub["B5_CrossRefs"] = round(4 * crossref)

    pts = sum(sub.values())
    pts = max(0, min(20, pts))

    findings: list[str] = []
    if over_long:
        findings.append(
            f"{len(over_long)} context files over conciseness budget (>100 lines): "
            + ", ".join(f"{p.relative_to(repo)} ({ln})" for p, ln in over_long[:4])
        )
    if sub["B2_QuickCommands"] < 3:
        findings.append("too few bash code blocks — add quick commands")
    if sub["B3_KeyFiles"] < 3:
        findings.append("too few key file paths cited — list 3-5")
    if sub["B4_NonObvious"] < 3:
        findings.append("too few hidden-rule markers like Why/Note/Gotcha")
    if sub["B5_CrossRefs"] < 3:
        findings.append("too few cross-links between related modules / context")

    return CategoryScore(
        name="Context Document Quality",
        score=pts,
        max=20,
        evidence={
            "context_files": n,
            "max_lines": max(line_counts),
            "min_lines": min(line_counts),
        },
        sub_scores=sub,
        findings=findings,
    )


# ----------------------------------------------------------------------------
# C. Tribal Knowledge Externalization (Five-Question Framework)
# ----------------------------------------------------------------------------
def score_c(modules: list[Module], repo: Path) -> CategoryScore:
    if not modules:
        return CategoryScore(name="Tribal Knowledge Externalization", score=0, max=20)

    # Detect MEMORY.md / ADR / decisions
    has_memory = (repo / "MEMORY.md").exists()
    # Check Claude Code memory dir for project
    claude_mem_dir_hits = list(repo.glob(".claude/memory*"))
    adr_dirs = [
        repo / "docs" / "adr",
        repo / "docs" / "decisions",
        repo / "adr",
    ]
    has_adr = any(d.exists() for d in adr_dirs)
    has_tribal_store = has_memory or has_adr or bool(claude_mem_dir_hits)

    # Per-module Q1-Q4 from context file content
    q_pass = [0, 0, 0, 0, 0]  # Q1..Q5
    n = max(1, len(modules))
    for m in modules:
        if not m.context_file:
            continue
        text = read_text(m.context_file)
        if RE_PURPOSE_HEADING.search(text) or "owns" in text.lower() or "configures" in text.lower():
            q_pass[0] += 1
        if RE_PATTERN_HEADING.search(text):
            q_pass[1] += 1
        if RE_NON_OBVIOUS.search(text):
            q_pass[2] += 1
        if RE_DEPS_HEADING.search(text) or "depends on" in text.lower():
            q_pass[3] += 1

    # Q5: tribal store presence (binary, project-wide)
    q5_score = 4 if has_tribal_store else 0

    # Sum: each Q is 4 points max. Q1-Q4 = 4 * avg pass rate
    sub = {
        "C_Q1_Owns": round(4 * q_pass[0] / n),
        "C_Q2_Patterns": round(4 * q_pass[1] / n),
        "C_Q3_NonObvious": round(4 * q_pass[2] / n),
        "C_Q4_Dependencies": round(4 * q_pass[3] / n),
        "C_Q5_TribalStore": q5_score,
    }
    pts = sum(sub.values())
    pts = max(0, min(20, pts))

    findings: list[str] = []
    if not has_tribal_store:
        findings.append("no MEMORY.md / ADR / docs/decisions — no tribal-knowledge externalization store")
    if q_pass[3] < n / 2:
        findings.append("Cross-module dependencies section missing in more than half of modules")
    if q_pass[1] < n / 2:
        findings.append("Common modification patterns section missing")

    return CategoryScore(
        name="Tribal Knowledge Externalization",
        score=pts,
        max=20,
        evidence={
            "memory_md": has_memory,
            "adr": has_adr,
            "modules_total": n,
            "q1_owns": q_pass[0],
            "q2_patterns": q_pass[1],
            "q3_nonobvious": q_pass[2],
            "q4_deps": q_pass[3],
        },
        sub_scores=sub,
        findings=findings,
    )


# ----------------------------------------------------------------------------
# D. Cross-Module Dependency & Data Flow Mapping
# ----------------------------------------------------------------------------
def score_d(repo: Path, context_files: list[Path]) -> CategoryScore:
    has_arch = any((repo / p).exists() for p in (
        "ARCHITECTURE.md", "docs/architecture.md", "docs/ARCHITECTURE.md",
        "docs/dependency-graph.md", "docs/data-flow.md",
    ))
    has_mermaid = any(RE_MERMAID.search(read_text(p)) for p in context_files)
    has_deps_section = sum(1 for p in context_files if RE_DEPS_HEADING.search(read_text(p)))
    has_workspace = any((repo / f).exists() for f in (
        "turbo.json", "nx.json", "pnpm-workspace.yaml", "lerna.json",
    ))

    pts = 0
    if has_arch:
        pts += 6
    if has_mermaid:
        pts += 3
    if has_deps_section >= max(1, len(context_files) // 2):
        pts += 4
    elif has_deps_section >= 1:
        pts += 2
    if has_workspace:
        pts += 2  # graph derivable
    pts = max(0, min(15, pts))

    findings: list[str] = []
    if not has_arch:
        findings.append("ARCHITECTURE.md / dependency map missing")
    if not has_mermaid:
        findings.append("no mermaid diagrams — no visual dependency representation")
    if has_deps_section == 0:
        findings.append("no cross-module dependency section in any context file")

    return CategoryScore(
        name="Cross-Module Dependency Mapping",
        score=pts,
        max=15,
        evidence={
            "architecture_doc": has_arch,
            "mermaid_diagrams": has_mermaid,
            "context_with_deps_section": has_deps_section,
            "monorepo_workspace": has_workspace,
        },
        findings=findings,
    )


# ----------------------------------------------------------------------------
# E. Verification & Quality Gates
# ----------------------------------------------------------------------------
def score_e(repo: Path, context_files: list[Path]) -> CategoryScore:
    sub: dict[str, int] = {}

    # E1 Reference accuracy: parse all path-like refs from context, verify existence
    total_refs = 0
    bad_refs: list[tuple[Path, str]] = []
    for p in context_files:
        text = read_text(p)
        for ref in set(RE_PATH_REF.findall(text)):
            total_refs += 1
            # try repo-relative and context-file-relative
            candidates = [repo / ref, p.parent / ref]
            if not any(c.exists() for c in candidates):
                bad_refs.append((p, ref))
    if total_refs == 0:
        sub["E1_RefAccuracy"] = 2  # neutral — nothing to verify
    else:
        accuracy = (total_refs - len(bad_refs)) / total_refs
        sub["E1_RefAccuracy"] = round(5 * accuracy)

    # E2 Critic / review infra
    has_codeowners = any((repo / p).exists() for p in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"))
    has_pr_template = any((repo / p).exists() for p in (
        ".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md",
    ))
    e2 = 0
    if has_codeowners:
        e2 += 2
    if has_pr_template:
        e2 += 2
    sub["E2_CriticReview"] = e2

    # E3 Task validation commands actually exist
    have_pkg_json = (repo / "package.json").exists()
    have_pyproject = (repo / "pyproject.toml").exists() or (repo / "apps/api/pyproject.toml").exists() or any(repo.glob("**/pyproject.toml"))
    have_make = (repo / "Makefile").exists()
    have_husky = (repo / ".husky").exists() or (repo / ".husky").is_dir()
    have_workflows = (repo / ".github" / "workflows").exists()
    e3 = 0
    if have_pkg_json or have_pyproject or have_make:
        e3 += 2
    if have_husky:
        e3 += 1
    if have_workflows:
        e3 += 1
    sub["E3_TaskValidation"] = min(4, e3)

    # E4 Prompt / agent eval tests
    has_evals = any((repo / p).exists() for p in ("evals", "benchmarks", "agent-evals", "prompts/test", "tests/agent"))
    sub["E4_PromptTests"] = 2 if has_evals else 0

    pts = sum(sub.values())
    pts = max(0, min(15, pts))

    findings: list[str] = []
    if bad_refs:
        sample = ", ".join(f"{p.relative_to(repo)}: {ref}" for p, ref in bad_refs[:4])
        findings.append(f"{len(bad_refs)} hallucinated paths (of {total_refs} refs) — e.g.: {sample}")
    if not has_codeowners and not has_pr_template:
        findings.append("no CODEOWNERS / PR template — no independent critic infra")
    if not has_evals:
        findings.append("no agent eval / prompt test directory — no AI regression catching")

    return CategoryScore(
        name="Verification & Quality Gates",
        score=pts,
        max=15,
        evidence={
            "ref_total": total_refs,
            "ref_broken": len(bad_refs),
            "codeowners": has_codeowners,
            "pr_template": has_pr_template,
            "ci_workflows": have_workflows,
            "husky": have_husky,
            "evals_dir": has_evals,
        },
        sub_scores=sub,
        findings=findings,
    )


# ----------------------------------------------------------------------------
# F. Freshness & Self-Maintenance
# ----------------------------------------------------------------------------
def latest_code_mtime(d: Path) -> float:
    latest = 0.0
    for r, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in IGNORE_DIRS and not x.startswith(".")]
        for f in files:
            if Path(f).suffix in CODE_EXTS:
                latest = max(latest, file_mtime(Path(r) / f))
    return latest


def score_f(modules: list[Module], repo: Path) -> CategoryScore:
    # Drift: how many modules' context is older than their newest code file
    drifted = 0
    measurable = 0
    for m in modules:
        if not m.context_file:
            continue
        ctx_mtime = file_mtime(m.context_file)
        code_mtime = latest_code_mtime(m.path)
        if code_mtime == 0:
            continue
        measurable += 1
        # 30-day staleness window
        if ctx_mtime + 30 * 86400 < code_mtime:
            drifted += 1
    drift_ratio = (drifted / measurable) if measurable else 0.0

    # CI / hook validators
    workflows = list((repo / ".github" / "workflows").glob("*.yml")) + list((repo / ".github" / "workflows").glob("*.yaml")) if (repo / ".github" / "workflows").exists() else []
    ctx_validation_workflow = any(
        re.search(r"context|docs|claude|adr|reference", read_text(w), re.IGNORECASE)
        for w in workflows
    )
    hook_validates_paths = (repo / ".husky" / "pre-commit").exists() or (repo / ".husky" / "pre-push").exists()

    pts = 0
    if measurable:
        # up to 6 pts for low drift
        pts += round(6 * (1 - drift_ratio))
    if ctx_validation_workflow:
        pts += 2
    if hook_validates_paths:
        pts += 2
    pts = max(0, min(10, pts))

    findings: list[str] = []
    if drifted:
        findings.append(f"context for {drifted}/{measurable} modules not updated for 30+ days after code changes")
    if not ctx_validation_workflow:
        findings.append("no context / docs validation step in CI")
    if not hook_validates_paths:
        findings.append("no path validation in pre-commit / pre-push hook")

    return CategoryScore(
        name="Freshness & Self-Maintenance",
        score=pts,
        max=10,
        evidence={
            "drifted_modules": drifted,
            "measurable_modules": measurable,
            "drift_ratio": round(drift_ratio, 3),
            "ctx_validation_workflow": ctx_validation_workflow,
            "hook_validates_paths": hook_validates_paths,
        },
        findings=findings,
    )


# ----------------------------------------------------------------------------
# G. Agent Performance Outcomes
# ----------------------------------------------------------------------------
def score_g(repo: Path) -> CategoryScore:
    eval_dirs = [p for p in ("evals", "benchmarks", "agent-evals", "agent-metrics") if (repo / p).exists()]
    metric_files = list(repo.glob("**/agent-results.json")) + list(repo.glob("**/.skill-eval.json"))
    metric_files = [m for m in metric_files if not any(seg in m.parts for seg in IGNORE_DIRS)]
    has_telemetry_hint = any(
        re.search(r"telemetry|opentelemetry|claude.*session|agent.*log",
                  read_text(p), re.IGNORECASE)
        for p in (repo / "CLAUDE.md", repo / "README.md", repo / "AGENTS.md")
        if p.exists()
    )

    pts = 0
    if eval_dirs:
        pts += 3
    if metric_files:
        pts += 1
    if has_telemetry_hint:
        pts += 1
    pts = max(0, min(5, pts))

    findings: list[str] = []
    if not eval_dirs and not metric_files:
        findings.append("no agent eval / benchmark directories or result files — no performance measurement infra")
    if not has_telemetry_hint:
        findings.append("no AI usage telemetry hints (session log / OpenTelemetry)")

    return CategoryScore(
        name="Agent Performance Outcomes",
        score=pts,
        max=5,
        evidence={
            "eval_dirs": eval_dirs,
            "metric_files": [str(p.relative_to(repo)) for p in metric_files],
            "telemetry_hint": has_telemetry_hint,
        },
        findings=findings,
    )


# ----------------------------------------------------------------------------
# Bonus / extras: large files, naming hints
# ----------------------------------------------------------------------------
def find_large_files(repo: Path, threshold: int = 300) -> list[tuple[Path, int]]:
    out: list[tuple[Path, int]] = []
    for p in walk_files(repo):
        if p.suffix not in CODE_EXTS:
            continue
        ln = count_lines(p)
        if ln > threshold:
            out.append((p, ln))
    out.sort(key=lambda x: -x[1])
    return out


# ----------------------------------------------------------------------------
# Grade & ROI
# ----------------------------------------------------------------------------
def grade_label(total: int) -> tuple[str, str]:
    if total >= 90:
        return "AI-Native", "green"
    if total >= 75:
        return "AI-Ready", "green"
    if total >= 60:
        return "AI-Assisted", "amber"
    if total >= 40:
        return "AI-Fragile", "amber"
    return "AI-Hostile", "red"


def derive_actions(report_partial: dict[str, CategoryScore], modules: list[Module],
                    large_files: list[tuple[Path, int]], repo: Path) -> list[Action]:
    actions: list[Action] = []
    A, B, C, D, E, F, G = (report_partial[k] for k in "ABCDEFG")

    # A — missing context files
    missing = [m.rel for m in modules if not m.has_context]
    if missing:
        actions.append(Action(
            title=f"Add CLAUDE.md to {len(missing)} core modules ({', '.join(missing[:3])}{'…' if len(missing) > 3 else ''})",
            category="A",
            effort="S", effort_hours=0.5 * len(missing),
            impact=f"~3 min per task × ~5 tasks/day saved → ~1-2 hr/week recovered per module",
            impact_score=9,
            priority=9 / max(0.5, 0.5 * len(missing)),
        ))

    # B — over-long context
    if B.evidence.get("max_lines", 0) > 100:
        actions.append(Action(
            title="Compress oversized CLAUDE.md to 25-35 lines (compass-not-encyclopedia)",
            category="B",
            effort="M", effort_hours=2.0,
            impact="faster agent context load + better visibility of key info",
            impact_score=7,
            priority=7 / 2.0,
        ))

    # C — no MEMORY/ADR
    if not C.evidence.get("memory_md") and not C.evidence.get("adr"):
        actions.append(Action(
            title="Externalize tribal knowledge via MEMORY.md or docs/adr/",
            category="C",
            effort="M", effort_hours=3.0,
            impact="externalizes senior-dependent decisions → fewer errors on new agent runs",
            impact_score=8,
            priority=8 / 3.0,
        ))

    # D — no architecture doc
    if not D.evidence.get("architecture_doc"):
        actions.append(Action(
            title="Add ARCHITECTURE.md or a mermaid dependency diagram",
            category="D",
            effort="M", effort_hours=2.5,
            impact="trace cross-module ripple → halve change-impact analysis time",
            impact_score=7,
            priority=7 / 2.5,
        ))

    # E1 — broken refs
    if E.evidence.get("ref_broken", 0) > 0:
        actions.append(Action(
            title=f"Fix {E.evidence['ref_broken']} hallucinated paths in context (referential trust)",
            category="E",
            effort="S", effort_hours=0.5,
            impact="prevents agent following bad paths — stale = worse than missing",
            impact_score=10,
            priority=10 / 0.5,
        ))

    # E — no path validation in CI
    if not F.evidence.get("ctx_validation_workflow") and not F.evidence.get("hook_validates_paths"):
        actions.append(Action(
            title="Add context path validation to CI or a pre-push hook",
            category="F",
            effort="S", effort_hours=1.0,
            impact="blocks stale references at merge time — prevents regressions",
            impact_score=8,
            priority=8 / 1.0,
        ))

    # 7 (large files) — included in B/C symptom but suggested separately
    huge = [(p, ln) for p, ln in large_files if ln > 500]
    if huge:
        sample = ", ".join(f"{p.relative_to(repo).as_posix()} ({ln})" for p, ln in huge[:3])
        actions.append(Action(
            title=f"Split {len(huge)} god files (>500 lines): {sample}",
            category="B",
            effort="L", effort_hours=2.5 * len(huge),
            impact=f"~5K-10K tokens saved per file + better edit accuracy",
            impact_score=6,
            priority=6 / max(2.5, 2.5 * len(huge)),
        ))

    # G — no eval infra
    if G.score < 3:
        actions.append(Action(
            title="Introduce an evals/ directory + representative task pass-rate measurement",
            category="G",
            effort="L", effort_hours=6.0,
            impact="enables AI regression measurement — quantifies improvement ROI itself",
            impact_score=6,
            priority=6 / 6.0,
        ))

    actions.sort(key=lambda a: -a.priority)
    return actions


# ----------------------------------------------------------------------------
# Generate insights
# ----------------------------------------------------------------------------
def generate_insights(cats: dict[str, CategoryScore], total: int) -> list[str]:
    out: list[str] = []
    grade, _ = grade_label(total)
    out.append(f"Total {total}/100 · grade {grade}")

    # weakest categories
    norm = sorted(cats.items(), key=lambda kv: kv[1].score / kv[1].max)
    weakest = norm[:2]
    for k, c in weakest:
        out.append(f"Lowest category: {k} {c.name} {c.score}/{c.max}")

    # E1 hallucination is special
    e = cats.get("E")
    if e and e.evidence.get("ref_broken", 0) > 0:
        out.append(
            f"⚠️  {e.evidence['ref_broken']} hallucinated paths in context — Meta standard says it must be 0"
        )

    # F freshness
    f = cats.get("F")
    if f and f.evidence.get("drift_ratio", 0) > 0.3:
        out.append(f"high context drift ({f.evidence['drift_ratio']:.0%}) — stale risk")

    return out


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def git_branch(repo: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build_report(repo: Path) -> Report:
    modules = find_core_modules(repo)
    context_files = find_all_context_files(repo)
    root_claude = find_root_claude(repo)
    large_files = find_large_files(repo, 300)

    cats = {
        "A": score_a(modules, root_claude),
        "B": score_b(context_files, repo),
        "C": score_c(modules, repo),
        "D": score_d(repo, context_files),
        "E": score_e(repo, context_files),
        "F": score_f(modules, repo),
        "G": score_g(repo),
    }
    total = sum(c.score for c in cats.values())
    grade, color = grade_label(total)
    actions = derive_actions(cats, modules, large_files, repo)
    insights = generate_insights(cats, total)

    return Report(
        meta={
            "repo": repo.name,
            "path": str(repo.resolve()),
            "scored_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "git_branch": git_branch(repo),
            "rubric_version": "v2-100pt",
            "modules_total": len(modules),
            "context_files_total": len(context_files),
            "large_files_300plus": len(large_files),
        },
        total=total,
        grade=grade,
        grade_color=color,
        categories=cats,
        insights=insights,
        actions=actions,
        extras={
            "modules": [asdict(m) | {"path": str(m.path), "context_file": str(m.context_file) if m.context_file else None} for m in modules],
            "large_files": [
                {"path": str(p.relative_to(repo).as_posix()), "lines": ln}
                for p, ln in large_files[:30]
            ],
        },
    )


def serialize(report: Report) -> dict[str, Any]:
    cats = {k: asdict(c) for k, c in report.categories.items()}
    return {
        "meta": report.meta,
        "total": report.total,
        "grade": report.grade,
        "grade_color": report.grade_color,
        "categories": cats,
        "insights": report.insights,
        "actions": [asdict(a) for a in report.actions],
        "extras": report.extras,
    }


def render_markdown(report: Report) -> str:
    lines = []
    lines.append(f"# AI-Readiness Audit · {report.meta['repo']}")
    lines.append("")
    lines.append(f"**Score:** {report.total}/100 · **Grade:** {report.grade}")
    lines.append(f"**Branch:** `{report.meta['git_branch']}` · **Scored:** {report.meta['scored_at']}")
    lines.append(f"**Modules:** {report.meta['modules_total']} · **Context files:** {report.meta['context_files_total']} · **Large files (>300 ln):** {report.meta['large_files_300plus']}")
    lines.append("")

    lines.append("## Category Scores")
    lines.append("")
    lines.append("| Cat | Name | Score |")
    lines.append("|-----|------|-------|")
    for k, c in report.categories.items():
        lines.append(f"| {k} | {c.name} | **{c.score}/{c.max}** |")
    lines.append("")

    lines.append("## Insights")
    for ins in report.insights:
        lines.append(f"- {ins}")
    lines.append("")

    lines.append("## Findings (per category)")
    for k, c in report.categories.items():
        if not c.findings:
            continue
        lines.append(f"### {k}. {c.name}  ({c.score}/{c.max})")
        for f in c.findings:
            lines.append(f"- {f}")
    lines.append("")

    lines.append("## Top Actions (ranked by ROI)")
    lines.append("")
    lines.append("| # | Effort | Action | Impact |")
    lines.append("|---|--------|--------|--------|")
    for i, a in enumerate(report.actions[:8], 1):
        lines.append(f"| {i} | {a.effort} ({a.effort_hours:.1f} hr) | [{a.category}] {a.title} | {a.impact} |")
    lines.append("")

    if report.extras["large_files"]:
        lines.append("## Large Files (>300 lines)")
        for lf in report.extras["large_files"][:10]:
            lines.append(f"- {lf['path']} — **{lf['lines']}** lines")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("repo", nargs="?", default=".", help="repo path (default: cwd)")
    p.add_argument("--json", dest="json_out", help="write JSON report to this path")
    p.add_argument("--markdown", action="store_true", help="emit markdown to stdout (default)")
    p.add_argument("--quiet", action="store_true", help="suppress stdout output")
    args = p.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"error: repo path not found: {repo}", file=sys.stderr)
        return 2

    report = build_report(repo)
    payload = serialize(report)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.quiet:
        if args.json_out and not args.markdown:
            # default: when writing json, also print summary
            print(render_markdown(report))
        elif args.markdown or not args.json_out:
            print(render_markdown(report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
