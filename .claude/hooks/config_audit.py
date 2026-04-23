"""config_audit.py -- ConfigChange hook: log when settings/skills change.

Fires on the ConfigChange event whenever .claude/settings.json, skills,
or other config files are modified during a session.  Appends a timestamped
entry to a local audit log so changes are traceable.

Per Anthropic best practice: https://code.claude.com/docs/en/hooks-guide
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    source = hook_input.get("source", "unknown")
    file_path = hook_input.get("file_path", "unknown")
    session_id = hook_input.get("session_id", "unknown")

    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "timestamp": ts,
        "source": source,
        "file": file_path,
        "session": session_id[:8] if len(session_id) > 8 else session_id,
    }

    # Append to audit log
    log_path = Path.home() / ".claude" / "config-audit.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Non-critical — don't block on log failure

    return 0


if __name__ == "__main__":
    sys.exit(main())
