"""threshold_commit.py -- PostToolUse hook: auto-commit + push when change thresholds are met.

Fires after Edit or Write tool calls. Checks two conditions against the working tree:
  1. Total lines changed (insertions + deletions) > 200
  2. Pending files in source control > 2

If EITHER condition is met: stage tracked files, commit with stats summary,
and push to origin main.

Never blocks (exit 0 always). Skips on merge conflicts or clean tree.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


_PORCELAIN_LINE = re.compile(r"^.{2}\s+(.+?)\s*$")


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run cmd in cwd, return (returncode, combined-output).

    Uses rstrip() (not strip()) so leading whitespace is preserved.
    `git status --porcelain` output begins with significant whitespace
    (e.g. ' M filename' for unstaged-modified files). A prior version
    used .strip() and produced corrupt filenames on the first line --
    see report/failure_log.md (2026-05-24) for the bug autopsy.
    """
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=20,
        )
        return r.returncode, (r.stdout + r.stderr).rstrip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, ""


def _get_diff_stats(repo_root: Path) -> tuple[int, int]:
    """Return (total_insertions, total_deletions) across all dirty tracked files."""
    rc, out = _run(["git", "diff", "--numstat", "HEAD"], repo_root)
    if rc != 0 or not out.strip():
        return 0, 0
    insertions = 0
    deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                insertions += int(parts[0]) if parts[0] != "-" else 0
                deletions += int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                pass
    return insertions, deletions


def _get_pending_files(repo_root: Path) -> list[str]:
    """Return list of dirty file paths from `git status --porcelain`.

    Uses a regex (status code = any 2 chars + whitespace + path) so the
    parse is robust to leading whitespace in any line. The prior version
    used fixed slicing line[3:] which combined with _run's earlier
    .strip() produced filenames missing their first character (e.g.
    'onfig/x.json' instead of 'config/x.json'). See failure_log autopsy.
    """
    rc, out = _run(["git", "status", "--porcelain"], repo_root)
    if rc != 0 or not out.strip():
        return []
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        m = _PORCELAIN_LINE.match(line)
        if m:
            paths.append(m.group(1))
    return paths


def _has_merge_conflict(repo_root: Path) -> bool:
    rc, out = _run(["git", "diff", "--name-only", "--diff-filter=U"], repo_root)
    return rc == 0 and bool(out.strip())


def _current_branch(repo_root: Path) -> str:
    rc, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    return out.strip() if rc == 0 else "unknown"


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    project_dir = hook_input.get("project_dir", ".")
    repo_root = Path(project_dir).resolve()

    rc, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], repo_root)
    if rc != 0:
        return 0

    if _has_merge_conflict(repo_root):
        return 0

    pending = _get_pending_files(repo_root)
    if not pending:
        return 0

    ins, dels = _get_diff_stats(repo_root)
    total_lines = ins + dels
    file_count = len(pending)

    # Check thresholds
    triggered_by = []
    if total_lines > 200:
        triggered_by.append(f"lines:{total_lines}(+{ins}/-{dels})")
    if file_count > 2:
        triggered_by.append(f"files:{file_count}")

    if not triggered_by:
        return 0

    # Stage all changes (tracked + untracked)
    rc, _ = _run(["git", "add", "-A"], repo_root)
    if rc != 0:
        return 0

    # Build commit message
    sample = ", ".join(pending[:4])
    if len(pending) > 4:
        sample += f" (+{len(pending) - 4} more)"
    trigger_str = " | ".join(triggered_by)
    msg = f"chore: threshold commit [{trigger_str}] -- {sample}"

    rc, _ = _run(["git", "commit", "-m", msg], repo_root)
    if rc != 0:
        return 0

    # Push to main
    branch = _current_branch(repo_root)
    if branch == "main":
        _run(["git", "push", "origin", "main"], repo_root)
    else:
        # On a feature branch — commit is done, flag that push needs manual merge
        result = {
            "message": (
                f"THRESHOLD COMMIT: committed ({trigger_str}) on branch '{branch}'. "
                "Not on main — push + merge required manually."
            )
        }
        json.dump(result, sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
