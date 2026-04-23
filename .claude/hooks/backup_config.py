"""backup_config.py -- PreToolUse hook: auto-backup config files before edit.

GLOBAL-014: Before altering ANY config file, copy original to ~/.claude/backups/.
Fires on Edit/Write tool calls targeting config files.
Does NOT block -- creates backup silently then allows the edit.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_PATTERNS = [
    "settings.json",
    "CLAUDE.md",
    "keybindings.json",
    "UserPref.json",
    "repos.json",
    "launch_configs.json",
    ".npmrc",
]


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool = hook_input.get("tool_name", "")
    if tool not in ("Edit", "Write"):
        return 0

    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    fpath = Path(file_path)
    if not fpath.exists():
        return 0  # New file, nothing to backup

    # Check if it matches a config pattern
    is_config = any(fpath.name == pat for pat in CONFIG_PATTERNS)
    if not is_config:
        return 0

    # Create backup
    backup_dir = Path.home() / ".claude" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_name = f"{fpath.stem}_{ts}{fpath.suffix}"
    dest = backup_dir / backup_name

    try:
        shutil.copy2(fpath, dest)
        print(
            f"GLOBAL-014: backed up {fpath.name} -> {dest}",
            file=sys.stderr,
        )
    except OSError as exc:
        print(f"GLOBAL-014 backup failed: {exc}", file=sys.stderr)

    return 0  # Always allow -- backup is non-blocking


if __name__ == "__main__":
    sys.exit(main())
