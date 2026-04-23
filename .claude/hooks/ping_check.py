"""ping_check.py -- Stop hook: blocks finish if unread pings across ANY repo.

CTRL-005: Before ending any session, all pings must be acknowledged.
Scans NP_ClaudeAgent + all repos in config/local_repos.json.
Exit 2 = BLOCK. Exit 0 = allow.

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
    """Parse ISO timestamp from .ping or .last-read file content.

    NOTE: This function is duplicated in pre_commit_guard.py (standalone hooks
    cannot import each other). Keep both copies in sync if this logic changes.
    """
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


def _load_repo_paths(project_dir: Path) -> dict[str, Path]:
    """Load repo name -> local path mapping from config."""
    config = project_dir / "config" / "local_repos.json"
    if not config.exists():
        return {}
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
        return {
            name: Path(path)
            for name, path in data.get("repos", {}).items()
        }
    except (json.JSONDecodeError, OSError):
        return {}


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
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path(hook_input.get("project_dir", ".")).resolve()

    unread: list[str] = []

    # Check self
    if check_pings(project_dir):
        unread.append(project_dir.name)

    # Check all configured repos
    repos = _load_repo_paths(project_dir)
    for name, path in repos.items():
        if not path.exists():
            continue
        if check_pings(path):
            unread.append(name)

    if unread:
        msg = (
            f"STOP BLOCKED (CTRL-005): unread ping(s) in {len(unread)} repo(s): "
            + ", ".join(unread[:5])
            + ". Run /upnote-protocol to acknowledge before finishing."
        )
        print(msg, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
