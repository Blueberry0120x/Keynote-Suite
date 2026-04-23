"""xplat_guard.py -- PreToolUse hook: blocks commit if XPLAT-001 violations exist.

Fires on Bash tool calls matching 'git commit'. Runs the AST-based
cross-platform guard (tests/test_xplat_guard.py) BEFORE the commit
executes. If any platform-gated code has dead else branches, the
commit is blocked.

Exit codes:
  0 = ALLOW (no violations)
  2 = BLOCK (XPLAT-001 violation found)

Enforces: GLOBAL-029 (XPLAT-001)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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
    test_file = repo_root / "tests" / "test_xplat_guard.py"

    if not test_file.exists():
        return 0  # Guard not present in this repo — allow

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-x", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root),
        )
        if result.returncode != 0:
            print(
                "COMMIT BLOCKED — XPLAT-001 violation detected.\n"
                "Platform-gated code has dead else branches.\n"
                f"{result.stdout.strip()}\n"
                "Fix: add working implementation for BOTH platforms.",
                file=sys.stderr,
            )
            return 2
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(
            f"XPLAT guard could not run: {exc}",
            file=sys.stderr,
        )
        # Don't block on infrastructure failure — the test suite
        # will still catch it.
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
