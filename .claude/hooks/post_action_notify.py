"""post_action_notify.py -- PostToolUse hook: auto-notify after major operations.

Fires on Bash tool calls. Detects major operations by matching commit
messages and CLI commands. Sends a GitHub notification via the
notify_github() utility.

"Major" means:
  - git commit with [DISPATCH-DONE], [BASELINE], [HOOKS-UPDATE],
    [CTRL-*], repo-sync, dev-check, logic-check, note-verify prefixes
  - py -m src.main commands: repo-sync, dev-check, logic-check,
    note-verify, launch, baseline, remote-invoke
  - /done completion gate pass

Exit 0 always (never blocks). Notification failure is logged, not fatal.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Patterns that indicate a major operation in a git commit message
_MAJOR_COMMIT_PATTERNS = [
    r"\[DISPATCH-DONE\]",
    r"\[BASELINE\]",
    r"\[HOOKS-UPDATE\]",
    r"\[CTRL-\d+\]",
    r"repo-sync",
    r"dev-check",
    r"logic-check",
    r"note-verify",
    r"baseline.*(deploy|push)",
    r"XPLAT-001",
    r"GLOBAL-\d+",
]

# CLI commands that are major operations
_MAJOR_CLI_PATTERNS = [
    r"py\s+-m\s+src\.main\s+repo-sync",
    r"py\s+-m\s+src\.main\s+dev-check",
    r"py\s+-m\s+src\.main\s+logic-check",
    r"py\s+-m\s+src\.main\s+note-verify",
    r"py\s+-m\s+src\.main\s+launch",
    r"py\s+-m\s+src\.main\s+baseline",
    r"py\s+-m\s+src\.main\s+remote-invoke\s+--start",
    r"py\s+-m\s+src\.main\s+remote-invoke\s+--reinvoke",
    r"py\s+tools/completion_gate\.py",
]

_COMPILED_COMMIT = [re.compile(p, re.IGNORECASE) for p in _MAJOR_COMMIT_PATTERNS]
_COMPILED_CLI = [re.compile(p) for p in _MAJOR_CLI_PATTERNS]


def _is_major_commit(command: str) -> str | None:
    """If the command is a git commit with a major tag, return the tag."""
    if "git commit" not in command:
        return None
    for pat in _COMPILED_COMMIT:
        m = pat.search(command)
        if m:
            return m.group(0)
    return None


def _is_major_cli(command: str) -> str | None:
    """If the command is a major CLI operation, return a short label."""
    for pat in _COMPILED_CLI:
        m = pat.search(command)
        if m:
            return m.group(0)
    return None


def _notify(task: str, detail: str = "") -> None:
    """Fire notification via notify_github if available, else gh CLI."""
    try:
        # Try importing the utility (available when running inside the repo)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from src.utils.utils import notify_github
        notify_github("COMPLETED", task, detail=detail)
    except (ImportError, Exception):
        # Fallback: direct gh CLI call
        try:
            body = f"✅ **COMPLETED:** {task}"
            if detail:
                body += f" | {detail}"
            subprocess.run(
                ["gh", "issue", "comment", "14",
                 "--repo", "Blueberry0120x/NP_ClaudeAgent",
                 "--body", body],
                capture_output=True,
                timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # No gh CLI — skip silently


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        return 0

    command = tool_input.get("command", "")
    tool_output = hook_input.get("tool_output", {})
    stdout = tool_output.get("stdout", "")

    # Check for major commit
    tag = _is_major_commit(command)
    if tag:
        _notify(f"Major commit: {tag}", detail=stdout[:200] if stdout else "")
        return 0

    # Check for major CLI operation
    label = _is_major_cli(command)
    if label:
        _notify(f"CLI operation: {label}", detail=stdout[:200] if stdout else "")
        return 0

    # Check for completion gate pass
    if "completion_gate" in command and "PASSED" in stdout:
        _notify("Completion gate PASSED")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
