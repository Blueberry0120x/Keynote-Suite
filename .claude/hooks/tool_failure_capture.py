"""tool_failure_capture.py -- PostToolUse hook: auto-document tool failures.

Fires after Bash/PowerShell tool calls. Detects non-zero exit codes or
error patterns in output and logs them to report/failure_log.md via
tools/failure_analyze.py, which also auto-ingests into Leviathan.

This closes the self-improvement loop: every tool failure is automatically
documented with a recursive why-chain, not just noted in passing.

Non-blocking: always exits 0 so Claude can continue working.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Exit codes that are expected/intentional -- don't log these as failures
_EXPECTED_EXITS: set[int] = {0, 130}  # 0=success, 130=Ctrl-C

# Patterns that indicate a real failure vs a handled error
_FAILURE_PATTERNS = [
    re.compile(r"Exit code ([1-9]\d*)"),         # Bash/PowerShell non-zero
    re.compile(r"Traceback \(most recent call"),  # Python crash
    re.compile(r"BLOCKED:.*gate.*failed"),        # Completion gate block
    re.compile(r"FATAL|CRITICAL.*error", re.I),  # Fatal errors
]

# Patterns that indicate expected/handled failure (skip logging)
_NOISE_PATTERNS = [
    re.compile(r"Exit code 1.*not found", re.I),     # command not found
    re.compile(r"no such file or directory", re.I),
    re.compile(r"git.*nothing to commit"),
]

_TOOL_NAMES = {"Bash", "PowerShell"}
_ROOT = Path(__file__).resolve().parent.parent.parent


def _extract_exit_code(output: str) -> int | None:
    m = re.search(r"Exit code ([1-9]\d*)", output)
    if m:
        return int(m.group(1))
    return None


def _is_noise(output: str) -> bool:
    return any(p.search(output) for p in _NOISE_PATTERNS)


def _first_error_line(output: str) -> str:
    """Extract the most informative error line from output."""
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for line in lines:
        if any(kw in line.lower() for kw in ("error", "failed", "traceback", "blocked")):
            return line[:120]
    return lines[-1][:120] if lines else "unknown error"


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in _TOOL_NAMES:
        return 0

    output = hook_input.get("tool_output", "") or ""
    if not output:
        return 0

    # Detect failure
    exit_code = _extract_exit_code(output)
    has_failure_pattern = any(p.search(output) for p in _FAILURE_PATTERNS)

    if not has_failure_pattern and (exit_code is None or exit_code in _EXPECTED_EXITS):
        return 0  # No failure

    if _is_noise(output):
        return 0  # Expected / benign

    # Build why-chain from tool context
    tool_input = hook_input.get("tool_input", {})
    cmd_preview = ""
    if isinstance(tool_input, dict):
        raw = tool_input.get("command", tool_input.get("input", ""))
        cmd_preview = str(raw)[:80] if raw else ""

    error_summary = _first_error_line(output)
    exit_str = f"exit {exit_code}" if exit_code else "error pattern detected"
    what = f"{tool_name} failure ({exit_str}): {error_summary[:80]}"

    why_chain = [
        f"Tool {tool_name} returned {exit_str}",
        f"Command preview: {cmd_preview}" if cmd_preview else "Command not captured",
        f"Error output: {error_summary}",
        "Root cause: investigate the error details above",
    ]

    fa = _ROOT / "tools" / "failure_analyze.py"
    if not fa.exists():
        return 0

    try:
        subprocess.run(
            [
                sys.executable, str(fa),
                "--failure", what,
                "--why", *why_chain,
                "--fix", "Investigate error output and apply appropriate fix",
                "--prevention", f"Check {tool_name} output for {exit_str} pattern before proceeding",
                "--category", "tooling",
            ],
            cwd=str(_ROOT),
            timeout=30,
            capture_output=True,
        )
    except Exception:  # noqa: BLE001
        pass  # Never let hook crash Claude

    return 0


if __name__ == "__main__":
    sys.exit(main())
