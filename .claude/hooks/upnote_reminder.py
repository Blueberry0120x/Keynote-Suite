"""upnote_reminder.py -- PostToolUse hook: reminds to write upnote after git commit.

CTRL-005: Every cross-scope change MUST have a corresponding upnote + ping.
After any git commit, injects a reminder into Claude's context.
Does NOT block -- reminds so the agent writes the upnote.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")
    output = hook_input.get("tool_output", "")

    if "git commit" not in command:
        return 0
    if not output or "nothing to commit" in output:
        return 0
    if "[main " not in output and "create mode" not in output:
        return 0

    result = {
        "message": (
            "CTRL-005 REMINDER: You just committed. If this affects "
            "cross-repo state: (1) write upnote to controller-note/ "
            "and touch .ping, (2) log key findings to /memories/repo/ "
            "or /memories/. Per CTRL-005, no silent changes. "
            "Load skill 'upnote-protocol' for the full ordered workflow."
        ),
    }
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
