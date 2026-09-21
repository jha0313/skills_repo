"""Skill discovery and immutable source snapshots; never checkout/reset user state."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from core import EvalError, digest, hash_bytes, read_data

EXCLUDE = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    ".DS_Store",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


def skill_files(root):
    root = Path(root).resolve()
    files = []
    for path in sorted(root.rglob("*")):
        if any(p in EXCLUDE for p in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            raise EvalError(
                f"평가 소스의 심볼릭 링크는 실제 파일 사본으로 바꿔야 합니다: {path}"
            )
        if path.is_file() and not path.name.startswith("eval_criteria.yaml"):
            files.append(path)
    return files


def snapshot_hash(root):
    root = Path(root).resolve()
    return digest(
        {
            str(p.relative_to(root)): hash_bytes(p.read_bytes())
            for p in skill_files(root)
        }
    )


def discover(target, source=None):
    p = Path(target).expanduser()
    if p.is_file() and p.name == "SKILL.md":
        p = p.parent
    if not (p / "SKILL.md").is_file():
        roots = [
            Path.cwd() / ".claude/skills",
            Path.home() / ".claude/skills",
            Path.home() / ".agents/skills",
            Path.home() / ".codex/skills",
            Path.cwd(),
        ]
        roots += [
            Path(v).expanduser()
            for v in os.environ.get("SKILL_EVAL_SKILL_ROOTS", "").split(os.pathsep)
            if v
        ]
        candidates = []
        for root in roots:
            for q in (root / target, root / "skills" / target):
                if (q / "SKILL.md").is_file() and q.resolve() not in candidates:
                    candidates.append(q.resolve())
        # The current CLI is the source of truth for installed marketplace/cache paths.
        if shutil.which("claude"):
            listed = subprocess.run(
                ["claude", "plugin", "list", "--json"],
                text=True,
                capture_output=True,
                timeout=30,
            )
            try:
                inventory = json.loads(listed.stdout)

                def paths(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in (
                                "installPath",
                                "path",
                                "install_path",
                            ) and isinstance(v, str):
                                yield Path(v)
                            else:
                                yield from paths(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            yield from paths(v)

                for root in paths(inventory):
                    for q in (root / target, root / "skills" / target):
                        if (q / "SKILL.md").is_file() and q.resolve() not in candidates:
                            candidates.append(q.resolve())
            except json.JSONDecodeError:
                pass
        if len(candidates) != 1:
            raise EvalError(
                f"대상이 없거나 모호합니다: {target}. SKILL.md가 있는 정확한 디렉터리를 지정하세요. 후보: {candidates}"
            )
        p = candidates[0]
    p = p.resolve()
    writable = Path(source).expanduser().resolve() if source else p
    if not (writable / "SKILL.md").is_file():
        raise EvalError("--source에는 쓰기 가능한 소스 SKILL.md가 있어야 합니다")
    plugin_root = next(
        (q for q in [p, *p.parents] if (q / ".claude-plugin/plugin.json").is_file()),
        None,
    )
    plugin_name = (
        read_data(plugin_root / ".claude-plugin/plugin.json").get("name")
        if plugin_root
        else "evaluated-skill"
    )
    text = (p / "SKILL.md").read_text()
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise EvalError("대상에 YAML frontmatter가 없습니다")
    import yaml

    fm = yaml.safe_load(match[1])
    if not isinstance(fm, dict) or not fm.get("name") or not fm.get("description"):
        raise EvalError("대상 frontmatter에 name/description이 필요합니다")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", fm["name"]):
        raise EvalError("대상 스킬 name은 소문자로 된 이식 가능한 slug여야 합니다")
    contents = {
        str(f.relative_to(p)): f.read_text(errors="replace")
        for f in skill_files(p)
        if f.suffix
        in (".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".txt")
    }
    signals = {
        "mcp": bool(re.search(r"\bmcp__|\bMCP\b", str(contents))),
        "internal_cli": bool(
            re.search(r"fbcode|buck2|\bSEV\b|\bMeta CLI\b", str(contents))
        ),
        "source_control": bool(
            re.search(r"git (commit|push|worktree|checkout)", str(contents))
        ),
        "fixed_paths": bool(re.search(r"/Users/|/home/|/data/", str(contents))),
        "local_scripts": bool(list((p / "scripts").glob("*"))),
        "delegated_skills": bool(re.search(r"\bSkill\b|/\w+-\w+", text)),
    }
    revision = (
        subprocess.run(
            ["git", "-C", str(writable), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
        ).stdout.strip()
        or None
    )
    return {
        "name": fm["name"],
        "description": fm["description"],
        "frontmatter": fm,
        "installed_path": str(p),
        "source_path": str(writable),
        "revision": revision,
        "skill_hash": snapshot_hash(p),
        "contents": contents,
        "plugin_root": str(plugin_root) if plugin_root else None,
        "plugin_name": plugin_name,
        "snapshot_path": str(plugin_root or p),
        "snapshot_hash": snapshot_hash(plugin_root or p),
        "dependency_signals": signals,
        "automatic_local": sum(signals.values()) >= 3,
        "criteria_path": str(writable / "evals/eval_criteria.yaml"),
    }


def copy_tree(src, dst):
    src = Path(src).resolve()
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for p in skill_files(src):
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)
        out.chmod(p.stat().st_mode & 0o777)
