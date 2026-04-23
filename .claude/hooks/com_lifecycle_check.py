"""com_lifecycle_check.py -- PreToolUse hook: checks COM objects have try/finally.

GLOBAL-013: Any script using New-Object -ComObject MUST wrap in try/finally.
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

    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    stripped = re.sub(
        r"<<['\"]?EOF['\"]?\n.*?^EOF", "", stripped,
        flags=re.MULTILINE | re.DOTALL,
    )
    if "git commit" not in stripped:
        return 0

    project_dir = Path(hook_input.get("project_dir", ".")).resolve()

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

    violations: list[str] = []
    for fname in staged:
        fpath = project_dir / fname
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        if "New-Object -ComObject" in content or "New-Object  -ComObject" in content:
            if "finally" not in content:
                violations.append(fname)

    if violations:
        msg = (
            f"COMMIT BLOCKED (GLOBAL-013): {len(violations)} PS file(s) use "
            f"COM objects without try/finally: {', '.join(violations)}"
        )
        print(msg, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
