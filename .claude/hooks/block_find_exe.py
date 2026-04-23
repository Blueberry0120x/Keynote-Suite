"""block_find_exe.py -- PreToolUse hook: blocks find.exe and secret-hunting commands.

GLOBAL-027: NEVER use find.exe, subprocess find, or glob patterns that hunt
for .env, .pem, .key, credentials files. This triggers Microsoft Defender
T1552.004 (Private Keys) and escalates to Stantec SOC.

Also blocks: wmic process (full CommandLine dump), tasklist /V (verbose).

Exit 2 = BLOCK the command.
"""
from __future__ import annotations

import json
import re
import sys

# Commands that MUST NEVER run — hard block
BLOCKED_PATTERNS = [
    # find.exe for any purpose (use Python pathlib.rglob instead)
    r"\bfind\.exe\b",
    r"\bfind\s+[/\\]",            # find / or find \
    r"\bfind\s+\.",               # find .
    r"\bfind\s+C:",              # find C:\...
    # Secret-hunting patterns
    r"\bfind\b.*\.(env|pem|key|secret|credential)",
    r"\bglob\b.*\.(env|pem|key|secret|credential)",
    r"\bls\b.*\.(env|pem|key|secret|credential)",
    # Process dumps that leak tokens
    r"\bwmic\s+process\b",
    r"\btasklist\s+/[Vv]\b",
    # Curl pipe to shell
    r"curl\s.*\|\s*(ba)?sh",
    r"iwr\s.*\|\s*iex",
    r"\bmshta\s+http",
]


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        return 0

    # Strip quoted strings, heredocs, and cat/echo bodies to avoid
    # false positives (e.g., mentioning find.exe in docs or commit msgs)
    stripped = re.sub(r'"[^"]*"', '""', command)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    # Strip heredoc bodies (<< 'DELIM' ... DELIM) for any delimiter
    stripped = re.sub(
        r"<<\s*['\"]?(\w+)['\"]?\s*\n.*?^\1",
        "", stripped,
        flags=re.MULTILINE | re.DOTALL,
    )
    # Strip cat > file ... EOF blocks (common pattern)
    stripped = re.sub(
        r"cat\s*>\s*\S+\s*<<.*", "", stripped,
        flags=re.DOTALL,
    )

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            msg = (
                f"BLOCKED by GLOBAL-027: command matches forbidden pattern "
                f"'{pattern}'. Use Python pathlib or Glob/Grep tools instead. "
                f"find.exe triggers Defender T1552.004 SOC alert."
            )
            print(msg, file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
