"""post_action_notify.py -- PostToolUse hook: auto-notify after major operations.

Fires on Bash tool calls. Detects major operations by matching commit
messages and CLI commands. Sends a GitHub notification via the
notify_github() utility.

"Major" means:
  - git commit with [DISPATCH-DONE], [BASELINE], [HOOKS-UPDATE],
    [CTRL-*], repo-sync, dev-check, logic-check, note-verify prefixes
  - py -m src.main commands: repo-sync, dev-check, logic-check,
    note-verify, launch, baseline, remote-invoke
  - /done completion gate pass

Exit 0 always (never blocks). Notification failure is logged, not fatal.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Patterns that indicate a major operation in a git commit message
_MAJOR_COMMIT_PATTERNS = [
    r"\[DISPATCH-DONE\]",
    r"\[BASELINE\]",
    r"\[HOOKS-UPDATE\]",
    r"\[CTRL-\d+\]",
    r"repo-sync",
    r"dev-check",
    r"logic-check",
    r"note-verify",
    r"baseline.*(deploy|push)",
    r"XPLAT-001",
    r"GLOBAL-\d+",
]

# CLI commands that are major operations
_MAJOR_CLI_PATTERNS = [
    r"py\s+-m\s+src\.main\s+repo-sync",
    r"py\s+-m\s+src\.main\s+dev-check",
    r"py\s+-m\s+src\.main\s+logic-check",
    r"py\s+-m\s+src\.main\s+note-verify",
    r"py\s+-m\s+src\.main\s+launch",
    r"py\s+-m\s+src\.main\s+baseline",
    r"py\s+-m\s+src\.main\s+remote-invoke\s+--start",
    r"py\s+-m\s+src\.main\s+remote-invoke\s+--reinvoke",
    r"py\s+tools/completion_gate\.py",
]

_COMPILED_COMMIT = [re.compile(p, re.IGNORECASE) for p in _MAJOR_COMMIT_PATTERNS]
_COMPILED_CLI = [re.compile(p) for p in _MAJOR_CLI_PATTERNS]


def _is_major_commit(command: str) -> str | None:
    """If the command is a git commit with a major tag, return the tag."""
    if "git commit" not in command:
        return None
    for pat in _COMPILED_COMMIT:
        m = pat.search(command)
        if m:
            return m.group(0)
    return None


def _is_major_cli(command: str) -> str | None:
    """If the command is a major CLI operation, return a short label."""
    for pat in _COMPILED_CLI:
        m = pat.search(command)
        if m:
            return m.group(0)
    return None


def _git_remote_owner_repo(repo_root: Path) -> tuple[str, str] | None:
    """Resolve (owner, repo) from git remote 'origin' URL. GLOBAL-004 compliant.

    Replaces the prior hardcoded 'Blueberry0120x/NP_ClaudeAgent' which broke
    every sister-repo notification by routing them to the controller's issue.
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=5,
        )
        url = (r.stdout or "").strip()
        if not url:
            return None
        # https://github.com/<owner>/<repo>.git  OR  git@github.com:<owner>/<repo>.git
        m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
        if not m:
            return None
        return m.group(1), m.group(2)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _notification_issue(repo_root: Path) -> str | None:
    """Per-repo notification issue number. None = no notification configured."""
    cfg = repo_root / ".claude" / "notification.json"
    if not cfg.exists():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        issue = data.get("issue")
        return str(issue) if issue else None
    except (json.JSONDecodeError, OSError):
        return None


def _notify(task: str, detail: str = "") -> None:
    """Fire notification scoped to the CURRENT repo's GitHub origin.

    GLOBAL-004 fix: owner/repo resolved from `git remote get-url origin`
    instead of hardcoded `Blueberry0120x/NP_ClaudeAgent`. Issue number from
    per-repo `.claude/notification.json` (no file -> skip silently). This
    closes the cross-repo notification spam discovered in Lane 4 audit.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    owner_repo = _git_remote_owner_repo(repo_root)
    if owner_repo is None:
        return  # not a git repo; nowhere to notify

    issue = _notification_issue(repo_root)
    if issue is None:
        return  # per-repo notification not configured; skip

    owner, repo = owner_repo
    try:
        body = f"COMPLETED: {task} [{repo}]"
        if detail:
            body += f"\n\n{detail}"
        subprocess.run(
            ["gh", "issue", "comment", issue,
             "--repo", f"{owner}/{repo}",
             "--body", body],
            capture_output=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # No gh CLI; skip silently


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name != "Bash":
        return 0

    command = tool_input.get("command", "")
    tool_output = hook_input.get("tool_output", {})
    stdout = tool_output.get("stdout", "")

    # Check for major commit
    tag = _is_major_commit(command)
    if tag:
        _notify(f"Major commit: {tag}", detail=stdout[:200] if stdout else "")
        return 0

    # Check for major CLI operation
    label = _is_major_cli(command)
    if label:
        _notify(f"CLI operation: {label}", detail=stdout[:200] if stdout else "")
        return 0

    # Check for completion gate pass
    if "completion_gate" in command and "PASSED" in stdout:
        _notify("Completion gate PASSED")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
