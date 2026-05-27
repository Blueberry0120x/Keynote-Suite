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


def _extract_name(command: str) -> str:
    """Extract the --name value from a command string."""
    m = re.search(r"--name\s+(\S+)", command)
    return m.group(1) if m else ""


def _pid_file_for(name: str) -> str:
    """Return the expected PID file path for a named session."""
    import os  # noqa: PLC0415
    safe = re.sub(r"[^\w.-]", "_", name)
    # tools/ dir is sibling of .claude/
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    tools_dir = os.path.join(os.path.dirname(hooks_dir), "tools")
    return os.path.join(tools_dir, f"remote_invoke_{safe}.pid")


def _session_already_running(name: str) -> bool:
    """Return True only if a PID file for this specific session name exists
    and the process is alive."""
    import os  # noqa: PLC0415
    pid_path = _pid_file_for(name)
    if not os.path.exists(pid_path):
        return False
    try:
        with open(pid_path, encoding="utf-8") as fh:
            pid_str = fh.read().strip()
        if not pid_str.isdigit():
            return False
        pid = int(pid_str)
        # Signal 0: check if process is alive (Windows uses tasklist fallback)
        pids = _get_claude_pids()
        return pid in pids
    except (OSError, ValueError):
        return False


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")

    # Only intercept remote-invoke --start launches (exact CTRL-008 pattern).
    is_remote_start = "remote-invoke" in command and "--start" in command

    # --reinvoke kills existing first — always allow
    if "--reinvoke" in command:
        return 0

    if not is_remote_start:
        return 0

    # Block only if THIS named session is already running
    name = _extract_name(command)
    if name and _session_already_running(name):
        print(
            f"BLOCKED (single-instance): session '{name}' is already running. "
            "Use --reinvoke to kill existing + start fresh, or --stop first.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
