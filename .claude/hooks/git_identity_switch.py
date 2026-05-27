"""git_identity_switch.py -- PreToolUse Bash hook (matcher: git commit).

Rewrites local git config user.name/user.email in the target repo to match
the current tenant's git_user / git_email BEFORE the commit lands. Prevents
silent identity drift across mid-session tenant switches.

See: GLOBAL-032, project_multi_designer_v5_architecture, src/identity/resolver.py

Non-blocking by design — if users.local.json is absent (fresh checkout) or
the command can't be parsed, exit 0 silently rather than fail the commit.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _extract_command(payload: dict) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    return tool_input.get("command", "")


def _is_git_commit(cmd: str) -> bool:
    return bool(re.search(r"\bgit\s+(?:-[^\s]+\s+)*commit\b", cmd))


def _repo_dir_from_command(cmd: str, cwd: str) -> Path:
    """Honor `git -C <path> commit ...` if present, else fall back to cwd."""
    m = re.search(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    if m:
        return Path(m.group(1).strip("\"'"))
    return Path(cwd) if cwd else Path.cwd()


def _resolve_identity():
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    try:
        from identity.resolver import resolve
    except Exception:
        return None
    try:
        return resolve()
    except Exception:
        return None


def _git_config(repo: Path, key: str, value: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "config", key, value],
        check=False, capture_output=True, text=True, timeout=5,
    )


def main() -> int:
    payload = _load_payload()
    cmd = _extract_command(payload)
    if not _is_git_commit(cmd):
        return 0

    idn = _resolve_identity()
    if idn is None or not idn.git_user or idn.git_user == "TBD":
        return 0

    cwd = payload.get("cwd") or payload.get("workingDirectory") or ""
    repo = _repo_dir_from_command(cmd, cwd)
    if not (repo / ".git").exists():
        return 0

    _git_config(repo, "user.name", idn.git_user)
    _git_config(repo, "user.email", idn.git_email)

    print(
        f"[git_identity_switch] {repo.name}: user.name={idn.git_user} "
        f"user.email={idn.git_email} (tenant={idn.tenant}, operator={idn.is_operator})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
