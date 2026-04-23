"""branch_naming.py -- PreToolUse hook: validates branch names (GLOBAL-003).

Fires on Bash commands containing 'git checkout -b' or 'git branch'.
Validates against allowed patterns. Exit 2 = BLOCK if invalid.
"""
from __future__ import annotations

import json
import re
import sys

ALLOWED_PATTERNS = [
    r"^main$",
    r"^dev\d+$",
    r"^feature/[a-z0-9][a-z0-9\-]+$",
    r"^claude/[a-z0-9][a-z0-9\-]+-dev\d+$",
    r"^fix/[a-z0-9][a-z0-9\-]+$",
    r"^refactor/[a-z0-9][a-z0-9\-]+$",
    r"^archived/.*$",
    r"^archived-.*$",
]

FORBIDDEN_NAMES = {"test", "temp", "wip", "stuff", "new-branch"}


def extract_branch_name(command: str) -> str | None:
    """Extract branch name from git checkout -b or git branch commands."""
    # git checkout -b <name>
    m = re.search(r"git\s+checkout\s+-b\s+(\S+)", command)
    if m:
        return m.group(1)
    # git branch <name> (but not git branch -d or git branch -a)
    m = re.search(r"git\s+branch\s+(?!-[adDrm])(\S+)", command)
    if m:
        return m.group(1)
    # git switch -c <name>
    m = re.search(r"git\s+switch\s+-c\s+(\S+)", command)
    if m:
        return m.group(1)
    return None


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    if hook_input.get("tool_name") != "Bash":
        return 0

    command = hook_input.get("tool_input", {}).get("command", "")
    branch = extract_branch_name(command)
    if not branch:
        return 0

    # Check forbidden
    if branch.lower() in FORBIDDEN_NAMES:
        print(
            f"BLOCKED (GLOBAL-003): forbidden branch name '{branch}'. "
            f"Use feature/*, fix/*, claude/*-dev*, or dev*.",
            file=sys.stderr,
        )
        return 2

    # Check uppercase
    if branch != branch.lower() and not branch.startswith("archived"):
        print(
            f"BLOCKED (GLOBAL-003): branch '{branch}' has uppercase. "
            "Use kebab-case (lowercase with hyphens).",
            file=sys.stderr,
        )
        return 2

    # Check spaces
    if " " in branch:
        print(
            f"BLOCKED (GLOBAL-003): branch '{branch}' has spaces.",
            file=sys.stderr,
        )
        return 2

    # Check allowed patterns
    if not any(re.match(pat, branch) for pat in ALLOWED_PATTERNS):
        print(
            f"BLOCKED (GLOBAL-003): branch '{branch}' doesn't match any "
            "allowed pattern (main, dev*, feature/*, fix/*, claude/*-dev*, "
            "refactor/*).",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
