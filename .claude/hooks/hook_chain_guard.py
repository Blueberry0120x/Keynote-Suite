"""hook_chain_guard.py -- PreToolUse hook: mandatory reminder before modifying hooks/workflows.

Fires on Edit|Write targeting .claude/hooks/*.py or .github/workflows/*.yml.
Injects a reminder to trace the full hook interaction chain before proceeding.
Does NOT block — injects context so the agent reads all related hooks first.

Root cause: session 2026-03-30 introduced 3 structural conflicts because hooks
were written without tracing how they interact with existing hooks.
"""
from __future__ import annotations

import json
import sys
from pathlib import PurePosixPath, PureWindowsPath


_HOOK_PATTERNS = (
    ".claude/hooks/",
    ".claude\\hooks\\",
    ".github/workflows/",
    ".github\\workflows\\",
    "reference/best-practices/hooks-baseline/",
    "reference\\best-practices\\hooks-baseline\\",
)

_HOOK_EXTENSIONS = (".py", ".yml", ".yaml")


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    # Check if target is a hook or workflow file
    is_hook = any(pat in file_path for pat in _HOOK_PATTERNS)
    if not is_hook:
        return 0

    has_ext = any(file_path.endswith(ext) for ext in _HOOK_EXTENSIONS)
    if not has_ext:
        return 0

    result = {
        "message": (
            "HOOK-CHAIN GUARD: You are modifying a hook or workflow file. "
            "BEFORE proceeding, you MUST have read ALL hooks in "
            ".claude/settings.json and traced the interaction chain. "
            "Checklist: (1) Read settings.json hook wiring. "
            "(2) For PostToolUse hooks: verify they don't create state "
            "that PreToolUse hooks block on. "
            "(3) For workflow changes: verify path filters exclude "
            ".ping/.last-read to prevent noise. "
            "(4) Test both positive AND negative cases. "
            "See report/hooks_audit_2026-03-30.md for known conflicts."
        ),
    }
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
