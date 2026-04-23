"""stop_gate.py -- Stop hook: blocks Claude from finishing if completion gate fails.

Fires on the 'Stop' event. Checks for stale artifacts and unread pings.
If any are found, exit 2 to BLOCK the stop and force continuation.

This is a LIGHTWEIGHT check (no pytest/pipeline) to avoid slowing every
response. The full gate (tools/completion_gate.py) is for pre-commit.

Uses content-based ISO timestamp comparison (not mtime) so that
git checkout/merge cannot cause false positives.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_ISO_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?)"
)


def _parse_ts(path: Path) -> datetime | None:
    """Parse ISO timestamp from .ping or .last-read file content."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        try:
            return datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc,
            )
        except OSError:
            return None
    if not text:
        return datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc,
        )
    m = _ISO_RE.search(text)
    if m:
        raw = m.group(1)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def check_stale(repo_root: Path) -> list[str]:
    """Return stale artifact paths in active directories."""
    patterns = ("*.bak", "*.old", "*.orig", "*.tmp", "*~", "*.copy", "*.rej")
    skip = {".venv", ".git", "node_modules", "report"}
    found: list[str] = []
    for pat in patterns:
        for hit in repo_root.rglob(pat):
            if any(part in hit.parts for part in skip):
                continue
            found.append(str(hit.relative_to(repo_root)))
    return found


def check_pings(repo_root: Path) -> bool:
    """Return True if unread pings exist (content-based comparison)."""
    ping = repo_root / "controller-note" / ".ping"
    last_read = repo_root / "controller-note" / ".last-read"
    ping_ts = _parse_ts(ping)
    if ping_ts is None:
        return False
    read_ts = _parse_ts(last_read)
    if read_ts is None:
        return True
    return ping_ts > read_ts


def main() -> int:
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Derive repo root
    project_dir = hook_input.get("project_dir", ".")
    repo_root = Path(project_dir).resolve()

    issues: list[str] = []

    # Check stale artifacts (lightweight — skip __pycache__ which regenerates)
    stale = check_stale(repo_root)
    if stale:
        issues.append(f"{len(stale)} stale artifact(s): {', '.join(stale[:3])}")

    # Check unread pings
    if check_pings(repo_root):
        issues.append("unread ping in controller-note/")

    if issues:
        msg = "STOP BLOCKED — fix before finishing: " + "; ".join(issues)
        print(msg, file=sys.stderr)
        return 2  # Exit 2 = BLOCK

    return 0  # Allow stop


if __name__ == "__main__":
    sys.exit(main())
