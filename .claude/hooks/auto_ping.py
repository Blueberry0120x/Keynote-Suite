"""auto_ping.py -- PostToolUse hook: auto-touches .ping when upnote is written.

CTRL-005 write-side enforcement: if any tool (Edit, Write, Bash) modifies
a file matching controller-note/*-upnote.md, automatically touch .ping
in the same directory with a fresh ISO timestamp.

This closes the gap where an agent writes an upnote but forgets to touch
.ping, making the note invisible to the controller and other agents.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


_UPNOTE_PATTERN = re.compile(
    r"controller-note[/\\].*-upnote\.md", re.IGNORECASE,
)


def _extract_paths(hook_input: dict) -> list[str]:
    """Extract file paths from Edit/Write tool input that might be upnote writes.

    Only Edit and Write are checked — the file_path is explicit and reliable.
    Bash detection was removed (R4): parsing command strings to infer upnote
    writes is fragile and misfires. Agents must use Edit/Write for upnotes.
    """
    paths: list[str] = []
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name in ("Edit", "Write"):
        fp = tool_input.get("file_path", "")
        if fp:
            paths.append(fp)

    return paths


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    # Only act on successful tool calls
    tool_output = hook_input.get("tool_output", "")
    if "error" in str(tool_output).lower()[:200]:
        return 0

    paths = _extract_paths(hook_input)
    touched: list[str] = []

    for p in paths:
        if not _UPNOTE_PATTERN.search(p):
            continue
        path = Path(p)
        note_dir = path.parent
        if not note_dir.exists():
            continue
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            # Touch .ping so other agents/controller detect the write
            (note_dir / ".ping").write_text(ts, encoding="utf-8")
            # Also update .last-read for self-pings — the writer already
            # knows what it wrote, so it counts as "read". Without this,
            # pre_commit_guard and ping_check block on self-generated pings.
            (note_dir / ".last-read").write_text(ts, encoding="utf-8")
            touched.append(str(note_dir))
        except OSError:
            continue

    if touched:
        dirs = ", ".join(touched)
        result = {
            "message": (
                f"CTRL-005 AUTO-PING: .ping + .last-read updated in {dirs}. "
                "Self-ping acknowledged automatically."
            ),
        }
        json.dump(result, sys.stdout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
