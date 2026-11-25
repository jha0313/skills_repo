#!/usr/bin/env python3
"""AI-Readiness Cartography — 저장소 채점기 (루브릭 v2.1, 100점, 7 카테고리).

저장소를 읽기만 하고, 점수·지적·액션을 JSON과 markdown으로 낸다.

    python3 -I score.py [저장소]                   # 기본: 현재 폴더, markdown 출력
    python3 -I score.py 저장소 --json score.json   # fill_template.py가 읽는 JSON도 저장
    python3 -I score.py 저장소 --lang en           # 문구만 영어로 (점수는 같다)

표준 라이브러리만 쓴다.
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
RE_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s)>\]\"'`]+")
# 확장자 순서(tsx가 ts보다 앞)와 끝 경계가 둘 다 있어야 page.tsx를 page.ts로 자르지 않는다.
# 앞 경계: ~/x, $HOME/x, <dir>/x, my-app/x의 app/x 같은 꼬리를 저장소 경로로 세지 않는다.
RE_PATH_REF = re.compile(
    r"(?<![A-Za-z0-9_./~$@%{}<>*\\-])"
    r"((?:(?:\.{1,2}/)+(?:[A-Za-z0-9_.-]+/)*|(?:\.?[A-Za-z0-9_][A-Za-z0-9_.-]*/)+)"
    r"[A-Za-z0-9_.-]+\.(?:tsx|ts|jsx|json|js|py|md|sql|yaml|yml|toml|html|css|sh|go|rs|java|kt|rb|php))"
    r"(?![A-Za-z0-9_])"
)
RE_BASH_FENCE = re.compile(r"```(?:bash|sh|shell|zsh|console)\s*\n([\s\S]*?)```", re.IGNORECASE)
RE_NON_OBVIOUS = re.compile(r"\b(Why:|Note:|Gotcha|Warning|Don't|Caveat|Important:|반드시|주의)", re.IGNORECASE)
RE_REL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://)([^)]+)\)")
RE_DEPS_HEADING = re.compile(r"^#+\s.*(depend|cross[- ]module|imports?|see also|related)", re.IGNORECASE | re.MULTILINE)
RE_PURPOSE_HEADING = re.compile(r"^#+\s.*(purpose|owns?|configures?|overview)", re.IGNORECASE | re.MULTILINE)
RE_PATTERN_HEADING = re.compile(r"^#+\s.*(pattern|how to|common change|workflow|recipe)", re.IGNORECASE | re.MULTILINE)
RE_MERMAID = re.compile(r"```mermaid", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Messages (ko, en) — 점수는 언어와 무관하고 문구만 바뀐다
# ----------------------------------------------------------------------------
LANGS = ("ko", "en")
MSG: dict[str, tuple[str, str]] = {
    "a.gap": ("context가 없는 핵심 module {n}개: {items}",
              "{n} core modules without context: {items}"),
    "a.nomodule": ("하위 폴더에서 코드가 든 module을 찾지 못함 (루트에 바로 둔 코드는 module로 세지 않음)",
                   "no code-bearing sub-directory found (code placed directly at the root is not counted as a module)"),
    "a.root": ("루트에 CLAUDE.md도 AGENTS.md도 없음 — 진입점 안내 없음",
               "no CLAUDE.md or AGENTS.md at the root — no entry-point briefing"),
    "b.none": ("context 파일이 하나도 없음", "no context files at all"),
    "b.long": ("100줄을 넘는 context {n}건: {items}", "{n} context files over 100 lines: {items}"),
    "b.quick": ("bash 코드 블록이 적음 — 바로 쓸 명령을 넣을 것", "too few bash code blocks — add ready-to-run commands"),
    "b.keyfiles": ("핵심 파일 경로가 적음 — 3~5개를 적을 것", "too few key file paths cited — list 3-5"),
    "b.nonobvious": ("Why·Note·Gotcha처럼 숨은 규칙을 알리는 표시가 적음",
                     "too few hidden-rule markers like Why/Note/Gotcha"),
    "b.crossref": ("관련 module·context로 가는 링크가 적음", "too few cross-links between related modules / context"),
    "c.store": ("MEMORY.md·ADR·docs/decisions가 없음 — 결정 이유를 남길 곳이 없음",
                "no MEMORY.md / ADR / docs/decisions — nowhere to keep decisions"),
    "c.deps": ("module 절반 이상에 의존성 절이 없음", "dependencies section missing in more than half of modules"),
    "c.patterns": ("module 절반 이상에 '흔한 수정 방법' 절이 없음",
                   "common modification patterns section missing in more than half of modules"),
    "d.arch": ("ARCHITECTURE.md나 의존성 지도가 없음", "ARCHITECTURE.md / dependency map missing"),
    "d.mermaid": ("context 파일에 mermaid 그림이 없음", "no mermaid diagram in the context files"),
    "d.section": ("어떤 context 파일에도 의존성 절이 없음", "no dependency section in any context file"),
    "e.refs": ("없는 경로 후보 {n}건 (참조 {total}건 중) — 예: {items}",
               "{n} candidate missing paths (of {total} refs) — e.g. {items}"),
    "e.review": ("CODEOWNERS도 PR 템플릿도 없음", "no CODEOWNERS / PR template"),
    "e.evals": ("에이전트 평가·프롬프트 시험 폴더가 없음", "no agent eval / prompt test directory"),
    "f.drift": ("module {total}개 중 {n}개의 context가 코드보다 30일 넘게 뒤처짐",
                "context for {n}/{total} modules is 30+ days behind the code"),
    "f.mtime": ("module {n}개는 git 커밋이 없어 파일 시각(mtime)으로 판정 — 복사·압축 해제 뒤에는 믿을 수 없음",
                "{n} modules have no git commits and were judged by file mtime — unreliable after a copy or unzip"),
    "f.shallow": ("얕은 clone이라 낡음을 판정하지 못함(중간 점수 3/6) — git fetch --unshallow 뒤 다시 실행",
                  "shallow clone, drift not judged (neutral 3/6) — run git fetch --unshallow and score again"),
    "f.ci": ("CI 워크플로에서 문서·context 검사로 보이는 낱말을 찾지 못함",
             "no word suggesting a docs / context check in CI workflows"),
    "f.hook": ("husky pre-commit·pre-push hook 파일이 없음", "no husky pre-commit / pre-push hook file"),
    "g.evals": ("에이전트 평가·benchmark 폴더나 결과 파일이 없음",
                "no agent eval / benchmark directories or result files"),
    "g.telemetry": ("AI 사용 기록의 단서가 없음 (session log / OpenTelemetry)",
                    "no AI usage telemetry hints (session log / OpenTelemetry)"),
    "i.total": ("총점 {total}/100 · 등급 {grade}", "Total {total}/100 · grade {grade}"),
    "i.weak": ("가장 낮은 카테고리: {k} {name} {score}/{max}", "Lowest category: {k} {name} {score}/{max}"),
    "i.refs": ("없는 경로 후보 {n}건 — 하나씩 열어 확인할 것", "{n} candidate missing paths — open and verify each one"),
    "i.drift": ("낡은 context 비율 {pct}", "context drift {pct}"),
    "act.a.t": ("핵심 module {n}개에 CLAUDE.md 또는 AGENTS.md 추가 ({items})",
                "Add CLAUDE.md or AGENTS.md to {n} core modules ({items})"),
    "act.a.i": ("에이전트가 들어갈 곳을 찾으려고 뒤지는 일을 줄인다", "less searching before the agent finds the right place"),
    "act.b.t": ("100줄을 넘는 context 파일을 줄이고 자세한 내용은 링크로",
                "Shorten context files over 100 lines and link out to details"),
    "act.b.i": ("매번 읽는 양이 줄고 핵심이 앞에 온다", "less text loaded every time, key points come first"),
    "act.c.t": ("MEMORY.md 또는 docs/adr/에 결정 이유 남기기", "Record decisions in MEMORY.md or docs/adr/"),
    "act.c.i": ("사람 머릿속 규칙을 에이전트도 찾아 읽을 수 있다", "rules kept in people's heads become readable by agents"),
    "act.d.t": ("ARCHITECTURE.md 또는 mermaid 의존성 그림 추가", "Add ARCHITECTURE.md or a mermaid dependency diagram"),
    "act.d.i": ("한 곳을 고치면 어디가 바뀌는지 따라갈 수 있다", "makes it possible to trace what a change affects"),
    "act.e.t": ("context의 없는 경로 후보 {n}건 확인하고 고치기", "Verify and fix {n} candidate missing paths in context"),
    "act.e.i": ("에이전트가 없는 파일을 찾아 헤매지 않는다", "stops agents from following paths that do not exist"),
    "act.f.t": ("CI나 pre-push hook에 context 경로 검사 추가", "Add context path validation to CI or a pre-push hook"),
    "act.f.i": ("틀린 경로를 합치기 전에 잡는다", "catches broken paths before merge"),
    "act.god.t": ("500줄 넘는 파일 {n}개 중 큰 것부터 나누기: {items}",
                  "Split the largest of {n} files over 500 lines: {items}"),
    "act.god.i": ("한 번에 읽는 양이 줄어든다", "less to read at once"),
    "act.g.t": ("evals/ 폴더와 대표 작업 통과율 측정 도입", "Introduce evals/ and measure pass rate on representative tasks"),
    "act.g.i": ("고친 것이 실제로 나아졌는지 잴 수 있다", "lets you measure whether a change helped"),
}
_lang = "ko"


def msg(key: str, **kw: Any) -> str:
    return MSG[key][LANGS.index(_lang)].format(**kw)


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
    """Top-level + apps/* + packages/* + services/* + src/(features|modules|domains)/*."""
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

    # 단일 앱의 도메인 폴더. 코드가 든 하위 폴더가 2개 이상일 때만 펼친다.
    domain_roots: list[Path] = []
    for pattern in ("features", "modules", "domains"):
        parent = repo / "src" / pattern
        if not parent.is_dir():
            continue
        domains = [d for d in sorted(parent.iterdir())
                   if d.is_dir() and d.name not in IGNORE_DIRS and not d.name.startswith(".") and code_file_count(d)]
        if len(domains) >= 2:
            domain_roots.append(parent)
            candidates.extend(domains)

    modules: list[Module] = []
    for d in candidates:
        # src는 펼친 도메인 밖의 코드만 센다. 남는 코드가 없으면 module이 아니다.
        code_count = code_file_count(d, skip=domain_roots)
        if code_count == 0:
            continue
        ctx_file, ctx_kind = pick_context_file(d)
        if ctx_file is None and d.parent in domain_roots:
            # 도메인은 src/features, src에 있는 안내를 물려받는다 (폴더마다 파일을 늘리게 하지 않는다)
            ctx_file, ctx_kind = pick_context_file(d.parent)
            if ctx_file is None:
                ctx_file, ctx_kind = pick_context_file(d.parent.parent)
        modules.append(Module(
            path=d,
            rel=d.relative_to(repo).as_posix(),
            code_files=code_count,
            has_context=ctx_file is not None,
            context_file=ctx_file,
            context_kind=ctx_kind,
        ))
    return modules


def code_file_count(d: Path, skip: list[Path] | tuple[()] = ()) -> int:
    count = 0
    for r, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in IGNORE_DIRS and not x.startswith(".") and Path(r) / x not in skip]
        count += sum(1 for f in files if Path(f).suffix in CODE_EXTS)
    return count


def pick_context_file(d: Path) -> tuple[Path | None, str]:
    for name in CONTEXT_FILES:
        p = d / name
        if p.exists():
            return p, name
    return None, ""


def find_all_context_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()  # CLAUDE.md -> AGENTS.md 링크를 두 번 세지 않는다
    for r, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in sorted(files):
            p = Path(r) / f
            if f in CONTEXT_FILES and p.resolve() not in seen:
                seen.add(p.resolve())
                out.append(p)
    return out


def find_path_refs(text: str) -> set[str]:
    return set(RE_PATH_REF.findall(RE_URL.sub(" ", text)))


def ref_exists(ref: str, ctx: Path, repo: Path) -> bool:
    """context 파일의 폴더부터 저장소 루트까지 올라가며 기준으로 삼아 본다."""
    base = ctx.parent
    while True:
        if (base / ref).exists():
            return True
        if base == repo:
            return False
        base = base.parent


def find_root_context(repo: Path) -> Path | None:
    """루트 진입점. CLAUDE.md와 AGENTS.md를 똑같이 본다."""
    for name in PRIMARY_CONTEXT:
        p = repo / name
        if p.exists():
            return p
    return None


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
def score_a(modules: list[Module], root_context: Path | None) -> CategoryScore:
    total = len(modules)
    covered = sum(1 for m in modules if m.has_context)
    coverage = covered / total if total else 0.0
    pts = round(coverage * 15)
    if root_context is None:
        pts = max(0, pts - 2)
    pts = max(0, min(15, pts))

    findings: list[str] = []
    if not modules:
        findings.append(msg("a.nomodule"))
    elif coverage < 1.0:
        gap_modules = [m.rel for m in modules if not m.has_context]
        findings.append(msg("a.gap", n=len(gap_modules), items=", ".join(gap_modules[:6])))
    if root_context is None:
        findings.append(msg("a.root"))

    return CategoryScore(
        name="AI Navigation & Coverage",
        score=pts,
        max=15,
        evidence={
            "core_modules": total,
            "covered_modules": covered,
            "coverage_ratio": round(coverage, 3),
            "root_context": root_context.name if root_context else None,
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
                             findings=[msg("b.none")])

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
        refs = find_path_refs(text)
        uniq = len(refs)
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
            msg("b.long", n=len(over_long),
                items=", ".join(f"{p.relative_to(repo)} ({ln})" for p, ln in over_long[:4]))
        )
    if sub["B2_QuickCommands"] < 3:
        findings.append(msg("b.quick"))
    if sub["B3_KeyFiles"] < 3:
        findings.append(msg("b.keyfiles"))
    if sub["B4_NonObvious"] < 3:
        findings.append(msg("b.nonobvious"))
    if sub["B5_CrossRefs"] < 3:
        findings.append(msg("b.crossref"))

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
        findings.append(msg("c.store"))
    if q_pass[3] < n / 2:
        findings.append(msg("c.deps"))
    if q_pass[1] < n / 2:
        findings.append(msg("c.patterns"))

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
        findings.append(msg("d.arch"))
    if not has_mermaid:
        findings.append(msg("d.mermaid"))
    if has_deps_section == 0:
        findings.append(msg("d.section"))

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
        for ref in sorted(find_path_refs(text)):
            total_refs += 1
            if not ref_exists(ref, p, repo):
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
        findings.append(msg("e.refs", n=len(bad_refs), total=total_refs, items=sample))
    if not has_codeowners and not has_pr_template:
        findings.append(msg("e.review"))
    if not has_evals:
        findings.append(msg("e.evals"))

    return CategoryScore(
        name="Verification & Quality Gates",
        score=pts,
        max=15,
        evidence={
            "ref_total": total_refs,
            "ref_broken": len(bad_refs),
            "broken_refs": [f"{p.relative_to(repo).as_posix()}: {ref}" for p, ref in bad_refs],
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
def git(repo: Path, *args: str) -> str:
    """읽기 전용 git. 대상 저장소 설정이 다른 프로그램을 부르지 않게 끈다. 실패하면 빈 문자열."""
    try:
        r = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "log.showSignature=false",
             "-C", str(repo), *args],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def commit_time(repo: Path, *pathspecs: str) -> float:
    out = git(repo, "log", "-1", "--format=%ct", "--", *pathspecs)
    return float(out) if out.isdigit() else 0.0


def module_times(m: Module, repo: Path) -> tuple[float, float, bool]:
    """(context 시각, 코드 시각, git 기준인가). 둘 다 커밋돼 있을 때만 커밋 시각을 쓴다."""
    target = m.context_file.resolve()  # 링크(CLAUDE.md -> AGENTS.md)면 실제 파일의 커밋을 본다
    ctx = (target if target.is_relative_to(repo) else m.context_file).relative_to(repo).as_posix()
    rel = re.sub(r"([\[\]*?\\])", r"\\\1", m.rel)
    ctx_time = commit_time(repo, f":(literal){ctx}")
    code_time = commit_time(repo, *(f"{rel}/*{ext}" for ext in sorted(CODE_EXTS))) if ctx_time else 0.0
    if ctx_time and code_time:
        return ctx_time, code_time, True
    return file_mtime(m.context_file), latest_code_mtime(m.path), False


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
    git_based = 0
    shallow = git(repo, "rev-parse", "--is-shallow-repository") == "true"
    for m in modules:
        if not m.context_file or shallow:
            continue
        ctx_time, code_time, from_git = module_times(m, repo)
        if code_time == 0:
            continue
        measurable += 1
        git_based += from_git
        # 30-day staleness window
        if ctx_time + 30 * 86400 < code_time:
            drifted += 1
    drift_ratio = (drifted / measurable) if measurable else 0.0
    if shallow:
        basis = "shallow"
    elif not measurable:
        basis = "none"
    else:
        basis = "git" if git_based == measurable else "mtime" if git_based == 0 else "git+mtime"

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
    elif shallow:
        pts += 3  # neutral — history is cut off, nothing to judge
    if ctx_validation_workflow:
        pts += 2
    if hook_validates_paths:
        pts += 2
    pts = max(0, min(10, pts))

    findings: list[str] = []
    if drifted:
        findings.append(msg("f.drift", n=drifted, total=measurable))
    if basis == "shallow":
        findings.append(msg("f.shallow"))
    elif "mtime" in basis:
        findings.append(msg("f.mtime", n=measurable - git_based))
    if not ctx_validation_workflow:
        findings.append(msg("f.ci"))
    if not hook_validates_paths:
        findings.append(msg("f.hook"))

    return CategoryScore(
        name="Freshness & Self-Maintenance",
        score=pts,
        max=10,
        evidence={
            "time_basis": basis,
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
    metric_files = [m for m in metric_files if not any(seg in m.relative_to(repo).parts for seg in IGNORE_DIRS)]
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
        findings.append(msg("g.evals"))
    if not has_telemetry_hint:
        findings.append(msg("g.telemetry"))

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


def effort_label(hours: float) -> str:
    return "S" if hours <= 1 else "M" if hours <= 4 else "L"


def derive_actions(report_partial: dict[str, CategoryScore], modules: list[Module],
                    large_files: list[tuple[Path, int]], repo: Path) -> list[Action]:
    actions: list[Action] = []
    A, B, C, D, E, F, G = (report_partial[k] for k in "ABCDEFG")

    # A — missing context files
    missing = [m.rel for m in modules if not m.has_context]
    if missing:
        actions.append(Action(
            title=msg("act.a.t", n=len(missing), items=", ".join(missing[:3]) + ("…" if len(missing) > 3 else "")),
            category="A",
            effort=effort_label(0.5 * len(missing)), effort_hours=0.5 * len(missing),
            impact=msg("act.a.i"),
            impact_score=9,
            priority=9 / max(0.5, 0.5 * len(missing)),
        ))

    # B — over-long context
    if B.evidence.get("max_lines", 0) > 100:
        actions.append(Action(
            title=msg("act.b.t"),
            category="B",
            effort="M", effort_hours=2.0,
            impact=msg("act.b.i"),
            impact_score=7,
            priority=7 / 2.0,
        ))

    # C — no MEMORY/ADR
    if not C.evidence.get("memory_md") and not C.evidence.get("adr"):
        actions.append(Action(
            title=msg("act.c.t"),
            category="C",
            effort="M", effort_hours=3.0,
            impact=msg("act.c.i"),
            impact_score=8,
            priority=8 / 3.0,
        ))

    # D — no architecture doc
    if not D.evidence.get("architecture_doc"):
        actions.append(Action(
            title=msg("act.d.t"),
            category="D",
            effort="M", effort_hours=2.5,
            impact=msg("act.d.i"),
            impact_score=7,
            priority=7 / 2.5,
        ))

    # E1 — broken refs
    if E.evidence.get("ref_broken", 0) > 0:
        actions.append(Action(
            title=msg("act.e.t", n=E.evidence["ref_broken"]),
            category="E",
            effort="S", effort_hours=0.5,
            impact=msg("act.e.i"),
            impact_score=10,
            priority=10 / 0.5,
        ))

    # E — no path validation in CI
    if not F.evidence.get("ctx_validation_workflow") and not F.evidence.get("hook_validates_paths"):
        actions.append(Action(
            title=msg("act.f.t"),
            category="F",
            effort="S", effort_hours=1.0,
            impact=msg("act.f.i"),
            impact_score=8,
            priority=8 / 1.0,
        ))

    # 7 (large files) — included in B/C symptom but suggested separately
    huge = [(p, ln) for p, ln in large_files if ln > 500]
    if huge:
        sample = ", ".join(f"{p.relative_to(repo).as_posix()} ({ln})" for p, ln in huge[:3])
        hours = 2.5 * len(huge[:3])  # 이름을 적은 파일만큼만 잡는다
        actions.append(Action(
            title=msg("act.god.t", n=len(huge), items=sample),
            category="B",
            effort=effort_label(hours), effort_hours=hours,
            impact=msg("act.god.i"),
            impact_score=6,
            priority=6 / hours,
        ))

    # G — no eval infra
    if G.score < 3:
        actions.append(Action(
            title=msg("act.g.t"),
            category="G",
            effort="L", effort_hours=6.0,
            impact=msg("act.g.i"),
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
    out.append(msg("i.total", total=total, grade=grade))

    # weakest categories
    norm = sorted(cats.items(), key=lambda kv: kv[1].score / kv[1].max)
    weakest = norm[:2]
    for k, c in weakest:
        out.append(msg("i.weak", k=k, name=c.name, score=c.score, max=c.max))

    # E1 missing paths get their own line
    e = cats.get("E")
    if e and e.evidence.get("ref_broken", 0) > 0:
        out.append(msg("i.refs", n=e.evidence["ref_broken"]))

    # F freshness
    f = cats.get("F")
    if f and f.evidence.get("drift_ratio", 0) > 0.3:
        out.append(msg("i.drift", pct=f"{f.evidence['drift_ratio']:.0%}"))

    return out


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def git_branch(repo: Path) -> str:
    return git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"


def build_report(repo: Path, lang: str = "ko") -> Report:
    global _lang
    _lang = lang
    repo = repo.resolve()
    modules = find_core_modules(repo)
    context_files = find_all_context_files(repo)
    root_context = find_root_context(repo)
    large_files = find_large_files(repo, 300)

    cats = {
        "A": score_a(modules, root_context),
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
            "scored_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "git_branch": git_branch(repo),
            "rubric_version": "v2.1-100pt",
            "lang": _lang,
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
            "modules": [
                {"rel": m.rel, "code_files": m.code_files,
                 "context_file": m.context_file.relative_to(repo).as_posix() if m.context_file else None}
                for m in modules
            ],
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
    p.add_argument("--lang", choices=LANGS, default="ko", help="message language; scores are identical (default: ko)")
    p.add_argument("--quiet", action="store_true", help="suppress stdout output")
    args = p.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2

    report = build_report(repo, args.lang)
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
