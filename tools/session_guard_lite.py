"""session_guard_lite.py -- Portable session guard for all project repos.

Runs at SessionStart. Checks:
  a) CLAUDE.md exists (BLOCKING)
  b) Unread pings in controller-note/ (BLOCKING)
  c) Warns about uncommitted work
  d) Warns about stale artifacts
  e) Kills OneDrive if running (GLOBAL-025)

Derives all paths from cwd — no hardcoded paths. Works in any repo.
Exit 0 = OK, Exit 1 = BLOCKED.

Uses content-based ISO timestamp comparison (not mtime) so that
git checkout/merge cannot cause false positives.
"""
from __future__ import annotations

import re
import socket
import subprocess
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


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=cwd, timeout=10)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def check_claude_md(repo_root: Path) -> bool:
    """Return True if CLAUDE.md is missing."""
    paths = [
        repo_root / ".claude" / "CLAUDE.md",
        repo_root / "CLAUDE.md",
    ]
    if any(p.exists() for p in paths):
        return False
    print("BLOCKED: No CLAUDE.md found")
    return True


def check_pings(repo_root: Path) -> bool:
    """Return True if unread pings exist (content-based comparison)."""
    ping = repo_root / "controller-note" / ".ping"
    last_read = repo_root / "controller-note" / ".last-read"
    ping_ts = _parse_ts(ping)
    if ping_ts is None:
        return False
    read_ts = _parse_ts(last_read)
    if read_ts is not None and ping_ts <= read_ts:
        return False
    print("UNREAD PING — run /upnote-protocol to acknowledge before proceeding")
    return True


def check_uncommitted(repo_root: Path) -> None:
    output = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if output:
        print(f"WARNING: {len(output.splitlines())} uncommitted file(s)")


def check_behind_remote(repo_root: Path) -> None:
    """Fetch and warn if current branch is behind remote."""
    branch = _run(["git", "branch", "--show-current"], cwd=repo_root)
    if not branch:
        return
    _run(["git", "fetch", "origin", branch], cwd=repo_root)
    behind = _run(
        ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
        cwd=repo_root,
    )
    if behind and behind.isdigit() and int(behind) > 0:
        print(
            f"ACTION REQUIRED: Branch '{branch}' is {behind} commit(s) "
            f"behind origin/{branch}. Run: git pull origin {branch}"
        )


def check_stale_artifacts(repo_root: Path) -> int:
    """Auto-clean stale artifacts at session start. Return count removed."""
    import shutil

    stale_patterns = (
        "*.bak", "*.old", "*.orig", "*.tmp", "*~",
        "*.copy", "*.rej", "*.pyc",
    )
    stale_dirs = ("__pycache__", ".pytest_cache")
    skip = {".venv", ".git", "node_modules", "report"}

    removed = 0

    for pat in stale_patterns:
        for hit in repo_root.rglob(pat):
            if any(part in hit.parts for part in skip):
                continue
            try:
                hit.unlink()
                removed += 1
            except OSError:
                pass

    for dirname in stale_dirs:
        for hit in repo_root.rglob(dirname):
            if any(part in hit.parts for part in skip):
                continue
            if hit.is_dir():
                try:
                    shutil.rmtree(hit)
                    removed += 1
                except OSError:
                    pass

    if removed:
        print(f"AUTO-CLEAN: removed {removed} stale artifact(s)")

    return removed


def kill_onedrive() -> None:
    if socket.gethostname().upper() in {"BLUEBERRY-MCP"}:
        return
    tasklist = _run(["tasklist", "/FI", "IMAGENAME eq OneDrive.exe"])
    if "OneDrive.exe" in tasklist:
        _run(["taskkill", "/F", "/IM", "OneDrive.exe"])
        print("OneDrive.exe killed (GLOBAL-025)")


def _slug_from_path(p: Path) -> str:
    """Derive Claude Code project slug from an absolute repo path.

    Example: C:\\Users\\NathanPham\\DevOps\\Ether -> c--Users-NathanPham-DevOps-Ether
    """
    s = str(p.resolve())
    if len(s) >= 2 and s[1] == ":":
        s = s[0].lower() + s[1:]
    for ch in (":", "\\", "/"):
        s = s.replace(ch, "-")
    return s


def check_memory_mirror(repo_root: Path) -> int:
    """Restore controller-note/agent-memory/ -> ~/.claude/projects/<slug>/memory/.

    Closes the GLOBAL-030 cross-machine + cross-profile gap: memory files
    committed to the mirror on Machine/Profile A are silently invisible to
    Machine/Profile B until restored. Run on every session start.

    Returns count of files restored. Non-blocking (warning only).
    """
    import shutil

    mirror_dir = repo_root / "controller-note" / "agent-memory"
    if not mirror_dir.exists():
        return 0

    home = Path.home()
    primary = _slug_from_path(repo_root)
    candidates = {primary}
    if "_" in repo_root.name:
        alt_path = repo_root.parent / repo_root.name.replace("_", "-")
        candidates.add(_slug_from_path(alt_path))
    candidates.add(f"d--DevOps-{repo_root.name}")
    candidates.add(f"d--DevOps-{repo_root.name.replace('_', '-')}")

    existing: list[tuple[float, Path]] = []
    for slug in candidates:
        cand = home / ".claude" / "projects" / slug / "memory"
        if not cand.exists():
            continue
        idx = cand / "MEMORY.md"
        try:
            mt = idx.stat().st_mtime if idx.exists() else cand.stat().st_mtime
        except OSError:
            mt = 0.0
        existing.append((mt, cand))

    if not existing:
        return 0
    existing.sort(reverse=True)
    auto_memory_dir = existing[0][1]

    mirror_files = {p.name for p in mirror_dir.glob("*.md")}
    local_files = {p.name for p in auto_memory_dir.glob("*.md")}
    missing_root = mirror_files - local_files

    mirror_chat = mirror_dir / "chat-history"
    local_chat = auto_memory_dir / "chat-history"
    missing_chat: set[str] = set()
    if mirror_chat.exists():
        local_chat.mkdir(parents=True, exist_ok=True)
        missing_chat = {p.name for p in mirror_chat.glob("*.md")} - {
            p.name for p in local_chat.glob("*.md")
        }

    index_diverged = False
    mirror_index = mirror_dir / "MEMORY.md"
    local_index = auto_memory_dir / "MEMORY.md"
    if mirror_index.exists() and local_index.exists():
        try:
            if mirror_index.read_bytes() != local_index.read_bytes():
                index_diverged = True
        except OSError:
            pass

    if not missing_root and not missing_chat and not index_diverged:
        return 0

    if (missing_root or missing_chat) and local_index.exists():
        backup_dir = home / ".claude" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        try:
            shutil.copy2(local_index, backup_dir / f"MEMORY_{stamp}.md")
        except OSError:
            pass

    restored = 0
    for name in sorted(missing_root):
        try:
            shutil.copy2(mirror_dir / name, auto_memory_dir / name)
            restored += 1
        except OSError:
            pass
    for name in sorted(missing_chat):
        try:
            shutil.copy2(mirror_chat / name, local_chat / name)
            restored += 1
        except OSError:
            pass

    if restored:
        print(f"MEMORY RESTORE: {restored} file(s) copied mirror -> auto-memory")
        preview = sorted(missing_root | missing_chat)
        for name in preview[:5]:
            print(f"  + {name}")
        if len(preview) > 5:
            print(f"  ... +{len(preview) - 5} more")

    if index_diverged:
        print(
            "MEMORY WARNING: MEMORY.md differs between mirror and auto-memory "
            "-- review and merge manually (auto-overwrite suppressed)"
        )

    return restored


def main() -> int:
    repo_root = Path.cwd().resolve()
    git_dir = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root)
    if git_dir:
        repo_root = Path(git_dir)

    print(f"session_guard: {repo_root.name}")
    print("-" * 40)

    kill_onedrive()
    missing = check_claude_md(repo_root)
    unread = check_pings(repo_root)
    check_uncommitted(repo_root)
    check_behind_remote(repo_root)
    check_memory_mirror(repo_root)
    check_stale_artifacts(repo_root)

    print("-" * 40)
    if missing:
        print("BLOCKED: Fix rule files before proceeding.")
        return 1

    if unread:
        print(
            "ACTION REQUIRED: Unread ping(s) detected. "
            "Run /upnote-protocol as your FIRST action this session."
        )

    print("Session guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
