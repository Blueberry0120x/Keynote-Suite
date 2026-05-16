"""memory_mirror.py -- PostToolUse hook: mirror auto-memory to git-tracked folder.

After ANY Write/Edit/MultiEdit on a file under the Claude Code auto-memory
folder for this project, copy the touched file into the repo's
`controller-note/agent-memory/` mirror so the memory survives machine swap,
fresh clone, or profile reset.

The hook reads JSON from stdin (Claude Code PostToolUse contract), inspects
the `tool_input.file_path` field, and if it sits inside this project's
auto-memory folder, copies the file (and refreshes the MEMORY.md index)
into the mirror.

Best-effort: non-blocking, exit 0 always. Failures are silent so they
never interrupt a session.

History: created 2026-05-16 after the MPL-Harbor incident where 2 hours
of Designer work was at risk because (a) MPL had zero memory, and (b)
auto-memory only lived at `~/.claude/projects/.../memory/`, lost on
machine swap. This hook closes that gap automatically.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _project_slug(repo_root: Path) -> str:
    """Convert D:\\DevOps\\NP_ClaudeAgent -> d--DevOps-NP-ClaudeAgent."""
    parts = repo_root.resolve().parts
    if not parts:
        return ""
    drive = parts[0].rstrip(":\\").lower()
    rest = [p.replace("_", "-") for p in parts[1:]]
    return f"{drive}-" + "-".join(rest)


def _auto_memory_root(repo_root: Path) -> Path:
    """Return the Claude Code auto-memory folder for this project."""
    import os

    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "")
    if not home.exists():
        return Path("")
    slug = _project_slug(repo_root)
    return home / ".claude" / "projects" / slug / "memory"


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

    auto_mem = _auto_memory_root(repo_root)
    if not auto_mem.exists():
        return 0

    try:
        touched = Path(file_path).resolve()
        rel = touched.relative_to(auto_mem)
    except (OSError, ValueError):
        return 0

    mirror_root = repo_root / "controller-note" / "agent-memory"
    mirror_root.mkdir(parents=True, exist_ok=True)
    dst = mirror_root / rel

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(touched, dst)
    except OSError:
        return 0

    # Always refresh the MEMORY.md index alongside individual files
    idx_src = auto_mem / "MEMORY.md"
    if idx_src.exists() and idx_src != touched:
        try:
            shutil.copy2(idx_src, mirror_root / "MEMORY.md")
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
