"""strictmode_check.py -- PreToolUse hook: checks PS files for StrictMode before commit.

GLOBAL-010: All .ps1/.psm1 files MUST have Set-StrictMode -Version Latest.
Fires on git commit. Scans staged PS files. Exit 2 = BLOCK if missing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0
    command = hook_input.get("tool_input", {}).get("command", "")

    # Strip quoted strings to avoid false positives
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    stripped = re.sub(
        r"<<['\"]?EOF['\"]?\n.*?^EOF", "", stripped,
        flags=re.MULTILINE | re.DOTALL,
    )
    if "git commit" not in stripped:
        return 0

    project_dir = Path(hook_input.get("project_dir", ".")).resolve()

    # Get staged PS files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, cwd=project_dir, timeout=10,
        )
        staged = [
            f for f in result.stdout.strip().splitlines()
            if f.endswith((".ps1", ".psm1"))
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0

    if not staged:
        return 0

    missing: list[str] = []
    for fname in staged:
        fpath = project_dir / fname
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        if "Set-StrictMode" not in content:
            missing.append(fname)

    if missing:
        msg = (
            f"COMMIT BLOCKED (GLOBAL-010): {len(missing)} PS file(s) missing "
            f"Set-StrictMode: {', '.join(missing)}"
        )
        print(msg, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
