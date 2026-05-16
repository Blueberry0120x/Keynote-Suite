"""memory_mirror.py -- PostToolUse hook: mirror auto-memory to git-tracked folder.

After ANY Write/Edit/MultiEdit on a file under the Claude Code auto-memory
folder for this project, copy the touched file into the repo's
`controller-note/agent-memory/` mirror so the memory survives machine swap,
fresh clone, or profile reset.

The hook reads JSON from stdin (Claude Code PostToolUse contract), inspects
the `tool_input.file_path` field, and if it sits inside this project's
auto-memory folder, copies the file (and refreshes the MEMORY.md index)
into the mirror.

Auto-memory location discovery: enumerate `~/.claude/projects/` for a folder
whose name ends with the repo name (raw or with underscores replaced by
dashes). This is robust against Claude Code's slug algorithm changes
across versions and case variations — far safer than trying to compute the
slug ourselves (the early version did and got it wrong, producing
`d-DevOps-NP-ClaudeAgent` when Claude Code uses `d--DevOps-NP-ClaudeAgent`).

Best-effort: non-blocking, exit 0 always. Failures are silent so they
never interrupt a session.

History: created 2026-05-16 after the MPL-Harbor incident where 2 hours
of Designer work was at risk because (a) MPL had zero memory, and (b)
auto-memory only lived at `~/.claude/projects/.../memory/`, lost on
machine swap. Initial version had a broken slug computation found by
the post-deploy dev-check; this version uses suffix-match discovery.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def _find_auto_memory(repo_root: Path) -> Path | None:
    """Locate this project's auto-memory folder by enumeration.

    Returns the most recently modified `memory/` folder under any project
    directory whose name ends with `<repo_name>` or `<repo_name with _ -> ->`.
    Cross-platform: uses USERPROFILE on Windows, HOME on POSIX.
    """
    home_env = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if not home_env:
        return None
    projects_dir = Path(home_env) / ".claude" / "projects"
    if not projects_dir.exists():
        return None

    repo_name = repo_root.name
    candidates = {repo_name, repo_name.replace("_", "-")}

    matches: list[tuple[Path, float]] = []
    for child in projects_dir.iterdir():
        if not child.is_dir():
            continue
        if not any(child.name.endswith(c) for c in candidates):
            continue
        mem = child / "memory"
        if mem.is_dir():
            try:
                matches.append((mem, mem.stat().st_mtime))
            except OSError:
                continue

    if not matches:
        return None

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[0][0]


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool = hook_input.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0

    file_path = (
        hook_input.get("tool_input", {}).get("file_path")
        or hook_input.get("tool_input", {}).get("path")
    )
    if not file_path:
        return 0

    project_dir = hook_input.get("project_dir", ".")
    repo_root = Path(project_dir).resolve()
    if not repo_root.exists():
        return 0

    auto_mem = _find_auto_memory(repo_root)
    if auto_mem is None:
        return 0

    try:
        touched = Path(file_path).resolve()
        rel = touched.relative_to(auto_mem)
    except (OSError, ValueError):
        return 0

    if not touched.is_file():
        return 0

    mirror_root = repo_root / "controller-note" / "agent-memory"
    try:
        mirror_root.mkdir(parents=True, exist_ok=True)
        dst = mirror_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(touched, dst)
    except OSError:
        return 0

    idx_src = auto_mem / "MEMORY.md"
    if idx_src.exists() and idx_src != touched:
        try:
            shutil.copy2(idx_src, mirror_root / "MEMORY.md")
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
