"""cross_repo_ping.py -- PostToolUse hook: check for unread pings after commits.

CTRL-005 mid-session re-scan: after every major task (commit, baseline push),
re-check .ping vs .last-read across all repos. Announces unread pings so
the agent can read upnotes before proceeding.

Non-blocking -- announces only, does not halt.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _extract_ts(raw: str) -> str:
    """Extract ISO timestamp from ping/last-read content.

    Handles: '2026-03-30T...' or 'pinged: 2026-03-30T...'
    Returns the first ISO-like substring, or empty string.
    """
    import re
    m = re.search(r"\d{4}-\d{2}-\d{2}T[\d:.+Z-]+", raw)
    return m.group(0) if m else ""


def _check_pings() -> list[str]:
    """Return list of repo names with unread pings."""
    repos_root = os.environ.get("REPOS_ROOT", "")
    if not repos_root:
        return []

    root = Path(os.path.expandvars(repos_root))
    if not root.is_dir():
        return []

    unread: list[str] = []
    try:
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            cn = child / "controller-note"
            ping = cn / ".ping"
            last = cn / ".last-read"

            if not ping.exists():
                continue

            try:
                p_raw = ping.read_text(encoding="utf-8").strip()
                l_ts = (
                    last.read_text(encoding="utf-8").strip()
                    if last.exists() else ""
                )
            except OSError:
                continue

            # Extract ISO timestamp from ping content
            # Formats: "2026-03-30T..." or "pinged: 2026-03-30T..."
            p_ts = _extract_ts(p_raw)
            l_ts = _extract_ts(l_ts)

            if p_ts and p_ts > l_ts:
                unread.append(child.name)
    except OSError:
        pass

    return unread


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")
    output = hook_input.get("tool_output", "")

    # Only trigger after successful git commit
    if "git commit" not in command:
        return 0
    if not output or "nothing to commit" in output:
        return 0

    unread = _check_pings()
    if not unread:
        return 0

    names = ", ".join(unread)
    result = {
        "message": (
            f"CTRL-005 PING DETECTED: Unread ping(s) from: {names}. "
            f"Read controller-note/ in those repos before proceeding."
        ),
    }
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
