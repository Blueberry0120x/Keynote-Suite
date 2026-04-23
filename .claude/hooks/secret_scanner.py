"""secret_scanner.py -- PostToolUse hook: scans output for leaked secrets.

Fires after Bash tool calls. Scans stdout for token patterns (GLOBAL-027).
If secrets detected, injects a warning into Claude's context.
Does NOT block — warns so Claude can redact.
"""
from __future__ import annotations

import json
import re
import sys

SECRET_PATTERNS = [
    (r"ghp_[a-zA-Z0-9]{36,}", "GitHub PAT (ghp_)"),
    (r"gho_[a-zA-Z0-9]{36,}", "GitHub OAuth (gho_)"),
    (r"github_pat_[a-zA-Z0-9_]{20,}", "GitHub PAT (github_pat_)"),
    (r"sk-[a-zA-Z0-9]{20,}", "API key (sk-)"),
    (r"cse_[a-zA-Z0-9]{20,}", "Claude session ID (cse_)"),
    (r"Bearer\s+[a-zA-Z0-9._\-]{20,}", "Bearer token"),
]


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        return 0

    output = hook_input.get("tool_output", "")
    if not output:
        return 0

    found: list[str] = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, output):
            found.append(label)

    if found:
        warning = (
            "WARNING: Potential secret(s) detected in output: "
            + ", ".join(found)
            + ". Per GLOBAL-027, NEVER display or log these. Redact immediately."
        )
        # Output as JSON context injection
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
            },
            "message": warning,
        }
        json.dump(result, sys.stdout)
        print(file=sys.stderr)
        print(f"SECRET SCAN: {', '.join(found)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
