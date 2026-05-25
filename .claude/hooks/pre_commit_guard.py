"""pre_commit_guard.py -- PreToolUse hook: auto-cleans stale artifacts before commit.

Fires on Bash tool calls matching 'git commit'. Auto-deletes stale artifacts
so they never land in a commit.

Ping blocking removed — ping_check.py (Stop hook) is the authoritative gate
for unread pings. Blocking at pre-commit was redundant friction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def check_stale(repo_root: Path) -> list[str]:
    """Return stale artifact paths (excluding pycache — gitignored)."""
    patterns = ("*.bak", "*.old", "*.orig", "*.tmp", "*~", "*.copy", "*.rej")
    skip = {".venv", ".git", "node_modules", "report"}
    found: list[str] = []
    for pat in patterns:
        for hit in repo_root.rglob(pat):
            if any(part in hit.parts for part in skip):
                continue
            found.append(str(hit.relative_to(repo_root)))
    return found


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0  # Can't parse — allow

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only intercept Bash calls that contain "git commit"
    if tool_name != "Bash":
        return 0
    command = tool_input.get("command", "")
    if "git commit" not in command:
        return 0

    project_dir = hook_input.get("project_dir", ".")
    repo_root = Path(project_dir).resolve()

    stale = check_stale(repo_root)
    if stale:
        for f in stale:
            try:
                (repo_root / f).unlink()
            except OSError:
                pass
        print(
            f"AUTO-CLEAN: removed {len(stale)} stale artifact(s) "
            f"before commit: {', '.join(stale[:5])}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
