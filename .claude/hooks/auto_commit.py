"""auto_commit.py -- Stop hook: auto-commit AND auto-push pending changes.

Fires on the 'Stop' event. If the working tree has uncommitted changes,
stages all files, commits, and pushes to origin so no work is silently lost —
not even to a disk failure or machine swap.

Does NOT block -- exit 0 always. Skips on merge conflicts or empty diffs.
Push is best-effort: if upstream is gone, missing, or auth fails, the commit
still stands locally and a later session can push.

History: prior version (pre-2026-05-16) only committed locally. A 2-hour
afternoon session of MPL onboarding work survived the commit step but never
got pushed -- the morning's `240fa98` commit sat local-only for hours while
a remote rebuild commit DELETED the same files. Designer rescue required.
This hook now pushes on every Stop event to close that gap.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path, timeout: int = 15) -> tuple[int, str]:
    """Run a git command and return (returncode, stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, ""


def _summarize(porcelain_lines: list[str], limit: int = 5) -> str:
    """Pull file paths out of `git status --porcelain` lines.

    Porcelain format is `XY <path>` where X and Y are status codes (one char
    each) and the field separator is a single space, then path starts. Older
    code did `line[3:]` which works for `XY path` but for single-status lines
    like ` M path` it left a leading space and produced `LAUDE.md` for
    ` M CLAUDE.md`. Split on whitespace instead.
    """
    paths: list[str] = []
    for line in porcelain_lines[:limit]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.append(parts[1].strip('"'))
    sample = ", ".join(paths)
    if len(porcelain_lines) > limit:
        sample += f" (+{len(porcelain_lines) - limit} more)"
    return sample


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

    rc, status = _run(["git", "status", "--porcelain"], repo_root)
    dirty = rc == 0 and bool(status.strip())

    if dirty:
        lines = status.strip().splitlines()
        sample = _summarize(lines)

        rc, _ = _run(["git", "add", "-u"], repo_root)
        if rc != 0:
            return 0

        msg = f"chore: auto-commit session changes -- {sample}"
        _run(["git", "commit", "-m", msg], repo_root)

    # Push unpushed commits (whether we just made one or earlier sessions did).
    # Best-effort: ignore failures so a missing upstream / auth issue doesn't
    # block the session. The commit is still on disk for next-session rescue.
    rc, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    if rc == 0 and branch and branch != "HEAD":
        rc, _ = _run(["git", "rev-list", "--count", "@{u}..HEAD"], repo_root)
        # If @{u} is missing, rev-list returns nonzero; --set-upstream first push.
        if rc != 0:
            _run(["git", "push", "--set-upstream", "origin", branch],
                 repo_root, timeout=60)
        else:
            _run(["git", "push", "origin", branch], repo_root, timeout=60)

    return 0  # Never block — informational commit + push only


if __name__ == "__main__":
    sys.exit(main())
