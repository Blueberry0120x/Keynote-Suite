"""single_instance.py -- PreToolUse hook: enforces single remote-invoke session.

Fires on Bash commands containing 'remote-invoke --start' or 'remote-control'.
Checks if a session is already running. If so, BLOCKS the launch.
Exit 2 = BLOCK (duplicate). Exit 0 = allow (no existing session).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


def _get_claude_pids() -> list[int]:
    """Return PIDs of running claude.exe remote-control processes."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq claude.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        pids = []
        for line in r.stdout.splitlines():
            if "claude.exe" not in line:
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
        return pids
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")

    # Only intercept remote-invoke --start or remote-control launches
    is_remote_start = (
        "remote-invoke" in command and "--start" in command
    ) or (
        "remote-control" in command and "claude" in command.lower()
    )

    # Also allow --reinvoke (which kills existing first)
    if "--reinvoke" in command:
        return 0

    if not is_remote_start:
        return 0

    # Check for existing claude.exe processes (excluding current session)
    pids = _get_claude_pids()

    # Filter: current process and its parent are not remote-control
    # Simple heuristic: if more than 2 claude.exe processes exist,
    # at least one is likely a remote-control session
    # (1 = this CLI session, 2+ = potential remote sessions)
    if len(pids) > 2:
        print(
            f"BLOCKED (single-instance): {len(pids)} claude.exe process(es) "
            f"already running (PIDs: {pids[:5]}). "
            "Use --reinvoke to kill existing + start fresh, "
            "or --stop first.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
