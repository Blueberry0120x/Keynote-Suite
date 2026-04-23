"""auto_commit.py -- Stop hook: auto-commit any pending changes at end of session turn.

Fires on the 'Stop' event. If the working tree has uncommitted changes,
stages all files and commits with a summary message so no work is silently lost.
Does NOT block -- exit 0 always. Skips on merge conflicts or empty diffs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git command and return (returncode, stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, ""


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = hook_input.get("project_dir", ".")
    repo_root = Path(project_dir).resolve()

    # Check git is available and we're in a repo
    rc, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], repo_root)
    if rc != 0:
        return 0

    # Skip if there are unresolved merge conflicts
    rc, conflicts = _run(
        ["git", "diff", "--name-only", "--diff-filter=U"], repo_root
    )
    if rc == 0 and conflicts:
        return 0

    # Check if working tree is dirty (tracked changes or untracked files)
    rc, status = _run(["git", "status", "--porcelain"], repo_root)
    if rc != 0 or not status.strip():
        return 0  # Nothing to commit

    # Build a short summary of what changed (first 5 paths)
    lines = status.strip().splitlines()
    sample = ", ".join(l[3:] for l in lines[:5])
    if len(lines) > 5:
        sample += f" (+{len(lines) - 5} more)"

    # Stage all changes
    rc, out = _run(["git", "add", "-A"], repo_root)
    if rc != 0:
        return 0

    # Commit
    msg = f"chore: auto-commit session changes -- {sample}"
    rc, out = _run(["git", "commit", "-m", msg], repo_root)

    return 0  # Never block — informational commit only


if __name__ == "__main__":
    sys.exit(main())
