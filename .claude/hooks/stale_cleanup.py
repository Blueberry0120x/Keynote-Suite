"""stale_cleanup.py -- SessionStart hook: auto-cleans pycache and warns on stale.

Fires at session start. Removes __pycache__ and .pytest_cache automatically.
Warns about other stale artifacts (*.bak, *.tmp, etc.) without removing them.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path(hook_input.get("project_dir", ".")).resolve()
    skip = {".venv", ".git", "node_modules"}

    # Auto-clean pycache and pytest_cache
    cleaned = 0
    for dirname in ("__pycache__", ".pytest_cache"):
        for hit in project_dir.rglob(dirname):
            if any(part in hit.parts for part in skip):
                continue
            if hit.is_dir():
                shutil.rmtree(hit, ignore_errors=True)
                cleaned += 1

    if cleaned:
        print(f"Auto-cleaned {cleaned} cache dir(s)", file=sys.stderr)

    # Warn about other stale artifacts
    patterns = ("*.bak", "*.old", "*.orig", "*.tmp", "*~")
    stale: list[str] = []
    for pat in patterns:
        for hit in project_dir.rglob(pat):
            if any(part in hit.parts for part in skip):
                continue
            if "report/archive" in str(hit):
                continue
            stale.append(str(hit.relative_to(project_dir)))

    if stale:
        print(
            f"WARNING: {len(stale)} stale artifact(s) in active paths. "
            f"Run /cleanup to remove.",
            file=sys.stderr,
        )

    return 0  # Never block session start for cleanup


if __name__ == "__main__":
    sys.exit(main())
