"""Universal pre-session guard for NP_ClaudeAgent (Controller).

Runs at session start to enforce critical rules PROGRAMMATICALLY:
    a) Check core rule files are present (BLOCKING — exit 1)
    b) Check unread pings in controller-note/ (WARNING)
    c) Warn about uncommitted work (git status)
    d) Warn about unpushed commits (git log @{u}..HEAD)
    e) Warn if not on main branch
    f) Kill OneDrive.exe if running (GLOBAL-025)
    g) Stale artifacts scan
    h) Check if branch is behind remote — ACTION REQUIRED: pull first
    j) Memory mirror restore — copy any mirror-only memory files into
       this machine's Claude Code auto-memory cache (closes GLOBAL-030
       cross-machine gap)
    k) Dispatch trigger — announce pending controller dispatch (ACTION REQUIRED)
    l) Exclusion violations — audit settings.json against exclusions registry (WARNING)

Derives all paths from cwd at runtime — no hardcoded paths.
Exit 0 = OK (warnings allowed), Exit 1 = blocking prerequisite missing.

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
from collections import Counter
from typing import List

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
    """Run a command, return stdout. Empty string on failure.

    Forces UTF-8 with replace on decode errors -- the default Windows cp1252
    codec dies on non-ASCII git output (commit messages with em-dashes etc.).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=10,
        )
        return (result.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def check_pings(repo_root: Path) -> bool:
    """Check controller-note/ pings. Return True if unread.

    Uses content-based ISO timestamp comparison, not mtime.
    """
    note_dir = repo_root / "controller-note"
    ping_file = note_dir / ".ping"
    last_read = note_dir / ".last-read"

    ping_ts = _parse_ts(ping_file)
    if ping_ts is None:
        return False

    read_ts = _parse_ts(last_read)
    if read_ts is not None and ping_ts <= read_ts:
        return False

    print("UNREAD PING -- run /upnote-protocol to acknowledge before proceeding")
    return True


def check_rules(repo_root: Path) -> bool:
    """Check required rule files exist. Return True if missing."""
    required = [
        repo_root / "CLAUDE.md",
        repo_root / "report" / "global_rules.md",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("RULE CHECK FAILED -- missing required rule file(s):")
        for path in missing:
            print(f"  - {path.relative_to(repo_root)}")
        return True

    print("Rule check passed.")
    return False


def check_uncommitted(repo_root: Path) -> None:
    """Warn about dirty working tree."""
    output = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if output:
        count = len(output.splitlines())
        print(f"WARNING: {count} uncommitted file(s) in working tree")


def check_unpushed(repo_root: Path) -> None:
    """Warn about commits not pushed to remote."""
    output = _run(
        ["git", "log", "--oneline", "@{u}..HEAD"],
        cwd=repo_root,
    )
    if output:
        count = len(output.splitlines())
        print(f"WARNING: {count} unpushed commit(s)")


def check_branch(repo_root: Path) -> None:
    """Warn if current branch is not main."""
    branch = _run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
    )
    if branch and branch != "main":
        print(f"WARNING: On branch '{branch}', not main")


def check_cross_repo_state(repo_root: Path) -> None:
    """Scan all sibling repos under REPOS_ROOT for uncommitted/unpushed work.

    The 2026-05-16 MPL-Harbor incident proved that single-repo guards are
    insufficient: the Controller session_guard was clean while
    Master-ProjectLibrary held 25 uncommitted files + 1 unpushed commit
    for hours. This scan walks every active repo in config/repos.json and
    surfaces any that are dirty so the agent can address them at session
    start, not days later.

    WARNING only (never blocking) — informational. The agent can choose to
    fix immediately or note for later.
    """
    import json
    import os

    repos_root = os.environ.get("REPOS_ROOT") or str(repo_root.parent)
    repos_root_p = Path(repos_root)

    config_path = repo_root / "config" / "repos.json"
    if not config_path.exists():
        return  # not in the controller repo; skip

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return

    active = config.get("repos", [])
    if not active:
        return

    dirty: list[str] = []
    unpushed: list[str] = []

    for name in active:
        rp = repos_root_p / name
        if not (rp / ".git").exists():
            continue
        status = _run(["git", "status", "--porcelain"], cwd=rp)
        if status:
            count = len(status.splitlines())
            dirty.append(f"{name}:{count}")
        ahead = _run(
            ["git", "rev-list", "--count", "@{u}..HEAD"], cwd=rp,
        )
        if ahead and ahead.isdigit() and int(ahead) > 0:
            unpushed.append(f"{name}:{ahead}")

    if dirty:
        print(
            "CROSS-REPO WARNING: uncommitted work in "
            + ", ".join(dirty)
        )
    if unpushed:
        print(
            "CROSS-REPO WARNING: unpushed commits in "
            + ", ".join(unpushed)
        )
    if not dirty and not unpushed:
        scanned = len([n for n in active if (repos_root_p / n / ".git").exists()])
        print(f"Cross-repo state: {scanned} repos clean")


def check_behind_remote(repo_root: Path) -> bool:
    """Fetch, auto-pull if behind, return True if pull was needed."""
    branch = _run(["git", "branch", "--show-current"], cwd=repo_root)
    if not branch:
        return False

    _run(["git", "fetch", "origin", branch], cwd=repo_root)

    behind = _run(
        ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
        cwd=repo_root,
    )
    if not (behind and behind.isdigit() and int(behind) > 0):
        return False

    print(f"Branch '{branch}' is {behind} commit(s) behind — auto-pulling...")
    result = _run(["git", "pull", "--rebase", "origin", branch], cwd=repo_root)
    if result is None:
        print("WARNING: Auto-pull failed — resolve manually before proceeding")
        return True
    print(f"Auto-pulled {behind} commit(s) from origin/{branch}")
    return True


def check_stale_artifacts(repo_root: Path) -> int:
    """Auto-clean stale artifacts at session start. Return count removed."""
    import shutil

    stale_patterns = (
        "*.bak", "*.old", "*.orig", "*.tmp", "*~",
        "*.copy", "*.rej", "*.pyc",
    )
    stale_dirs = ("__pycache__", ".pytest_cache")
    skip_dirs = {".venv", ".git", "node_modules", "report/archive"}

    removed = 0
    type_counts: Counter = Counter()

    for pattern in stale_patterns:
        for hit in repo_root.rglob(pattern):
            if any(part in hit.parts for part in skip_dirs):
                continue
            try:
                hit.unlink()
                type_counts[pattern] += 1
                removed += 1
            except OSError:
                pass

    for dirname in stale_dirs:
        for hit in repo_root.rglob(dirname):
            if any(part in hit.parts for part in skip_dirs):
                continue
            if hit.is_dir():
                try:
                    shutil.rmtree(hit)
                    type_counts[dirname] += 1
                    removed += 1
                except OSError:
                    pass

    if removed:
        print(f"AUTO-CLEAN: removed {removed} stale artifact(s)")
        _document_stale_pattern(repo_root, removed, type_counts)

    return removed


def _document_stale_pattern(
    repo_root: Path,
    count: int,
    type_counts: Counter,
) -> None:
    """Fire-and-forget: document stale artifact pattern via failure_analyze.py."""
    if count <= 3:
        return  # Skip trivial cleanup (pycache from prior run is normal)
    fa = repo_root / "tools" / "failure_analyze.py"
    if not fa.exists():
        return
    top = type_counts.most_common(3)
    type_summary = ", ".join(f"{t}:{c}" for t, c in top)
    try:
        subprocess.Popen(
            [
                sys.executable, str(fa),
                "--failure", f"Stale artifacts at session start: {count} files ({type_summary})",
                "--why",
                f"session_guard found {count} stale artifact(s) at session start",
                f"Top types: {type_summary}",
                "Artifacts were not cleaned up by the tool that created them",
                "Root cause: per-tool cleanup not wired; only session-start guard catches them",
                "--fix", f"Auto-cleaned {count} artifact(s)",
                "--prevention",
                "Wire cleanup into every tool that writes *.tmp/*.bak/pycache. "
                "Session_guard is a safety net, not a substitute for per-tool cleanup.",
                "--category", "operations",
            ],
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        pass


def _slug_from_path(p: Path) -> str:
    """Derive Claude Code project slug from an absolute repo path.

    Claude Code creates ~/.claude/projects/<slug>/ where <slug> is the
    absolute path with the drive letter lowercased and ':', '\\', '/'
    replaced by '-'. Example:
        C:\\Users\\NathanPham\\DevOps\\Ether  ->  c--Users-NathanPham-DevOps-Ether
        D:\\DevOps\\NP_ClaudeAgent           ->  d--DevOps-NP_ClaudeAgent
    """
    s = str(p.resolve())
    if len(s) >= 2 and s[1] == ":":
        s = s[0].lower() + s[1:]
    for ch in (":", "\\", "/"):
        s = s.replace(ch, "-")
    return s


def check_memory_mirror(repo_root: Path) -> int:
    """Restore mirror -> auto-memory when mirror has files local doesn't.

    Closes the GLOBAL-030 gap that surfaced 2026-05-20: cross-machine memory
    contributions land in controller-note/agent-memory/ on pull but the
    Claude Code auto-memory cache stays stale. Without this, every new
    feedback/project memory written on Machine A is invisible to Machine B
    until a manual fresh-machine restore.

    Behavior:
      - Diff *.md files in controller-note/agent-memory/ vs local auto-memory.
      - Mirror-only files: copy in (after timestamped MEMORY.md backup).
      - chat-history/ subfolder treated the same way.
      - MEMORY.md content divergence: WARN only, never auto-overwrite
        (the index may be diverged structurally; needs agent merge).

    Slug is derived from the actual repo path (works for any workspace
    layout: D:\\DevOps\\, C:\\Users\\<svc>\\DevOps\\, cross-profile, etc.).
    Legacy 'd--DevOps-<name>' slugs are also checked for back-compat with
    older machines that pre-date the workspace migration.

    Returns count of files restored. Non-blocking (warning only).
    """
    import shutil

    mirror_dir = repo_root / "controller-note" / "agent-memory"
    if not mirror_dir.exists():
        return 0

    home = Path.home()
    # Primary slug = derived from current absolute repo path. Also include
    # legacy 'd--DevOps-<name>' so machines still carrying the old slug get
    # restored. Two name variants for repos with '_' (Claude Code historically
    # alternated between '_' and '-' in the slug).
    primary = _slug_from_path(repo_root)
    candidates = {primary}
    if "_" in repo_root.name:
        alt_path = repo_root.parent / repo_root.name.replace("_", "-")
        candidates.add(_slug_from_path(alt_path))
    candidates.add(f"d--DevOps-{repo_root.name}")
    candidates.add(f"d--DevOps-{repo_root.name.replace('_', '-')}")
    existing: list[tuple[float, Path]] = []
    for slug in candidates:
        candidate = home / ".claude" / "projects" / slug / "memory"
        if not candidate.exists():
            continue
        idx = candidate / "MEMORY.md"
        try:
            mtime = idx.stat().st_mtime if idx.exists() else candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        existing.append((mtime, candidate))

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
        mirror_chat_files = {p.name for p in mirror_chat.glob("*.md")}
        local_chat_files = {p.name for p in local_chat.glob("*.md")}
        missing_chat = mirror_chat_files - local_chat_files

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
        backup_path = backup_dir / f"MEMORY_{stamp}.md"
        try:
            shutil.copy2(local_index, backup_path)
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


def check_dispatch_trigger(repo_root: Path) -> bool:
    """Announce pending controller dispatch if trigger file exists.

    The Controller writes ``controller-note/auto_dispatch.trigger`` when it
    dispatches tasks.  This makes it impossible for a session to silently
    miss a pending dispatch — the agent sees it at the very first prompt.

    Returns True if a pending dispatch was found.
    """
    trigger = repo_root / "controller-note" / "auto_dispatch.trigger"
    if not trigger.exists():
        return False
    try:
        summary = trigger.read_text(encoding="utf-8").strip()
    except OSError:
        summary = ""
    print("=" * 40)
    print("PENDING CONTROLLER DISPATCH")
    if summary:
        for line in summary.splitlines():
            print(f"  {line}")
    print("TYPE: 'controller dispatch' to execute")
    print("=" * 40)
    return True


def check_exclusion_violations(repo_root: Path) -> List[str]:
    """Audit settings.json against the exclusions registry.

    Reads ``controller-note/exclusions.json`` (deployed by CTRL-004) and
    checks whether any excluded hooks are present in ``.claude/settings.json``.
    Returns a list of violation strings so session_guard can warn.

    This closes the loop on the re-add problem: even if an audit agent adds
    a hook back, the next session start will surface it immediately.
    """
    exclusions_path = repo_root / "controller-note" / "exclusions.json"
    if not exclusions_path.exists():
        return []

    settings_path = repo_root / ".claude" / "settings.json"
    if not settings_path.exists():
        return []

    import json as _json

    try:
        excl_data = _json.loads(exclusions_path.read_text(encoding="utf-8"))
        settings_data = _json.loads(settings_path.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError):
        return []

    # Infer repo name from directory name
    repo_name = repo_root.name

    # Flatten hook identifiers present in settings
    present: set[str] = set()
    for _event, entries in settings_data.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    parts = cmd.replace('"', "").replace("'", "").split()
                    for part in parts:
                        if part.endswith(".py") or part.endswith(".ps1"):
                            present.add(Path(part).name)
                hook_type = hook.get("type", "")
                if hook_type and hook_type != "command":
                    present.add(hook_type)

    violations: List[str] = []
    for item in excl_data.get("entries", []):
        item_repo = item.get("repo", "")
        item_type = item.get("type", "")
        identifier = item.get("identifier", "")
        if (item_repo == repo_name or item_repo == "*") and item_type == "hook":
            if identifier in present:
                # Opt-in awareness: action=allow_optin entries permit specific
                # repos to wire the hook legitimately. Skip if this repo is in
                # the opt-in list. Inline (no src/ import) because this tool
                # is deployed to every repo and must stay standalone.
                if item.get("action") == "allow_optin":
                    optin_rel = item.get("optin_file", "")
                    if optin_rel and _repo_in_optin_file(repo_root, optin_rel, repo_name):
                        continue
                violations.append(
                    f"EXCLUSION VIOLATION: '{identifier}' in settings.json was "
                    f"intentionally removed on {item.get('removed_date', '?')}. "
                    f"Reason: {item.get('reason', '?')}"
                )
    return violations


def _repo_in_optin_file(repo_root: Path, optin_rel: str, repo_name: str) -> bool:
    """Return True if repo_name is listed in optin_repos of the JSON at optin_rel.

    optin_rel is relative to the repo root. Falls back to checking the
    Controller's NP_ClaudeAgent workspace if not present locally (so non-Controller
    repos can still resolve opt-ins from the canonical source).
    """
    import json as _json

    candidates = [repo_root / optin_rel]
    # If we're not in NP_ClaudeAgent, try the controller's copy via sibling lookup
    if repo_root.name != "NP_ClaudeAgent":
        sibling = repo_root.parent / "NP_ClaudeAgent" / optin_rel
        candidates.append(sibling)

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            continue
        if any(entry.get("repo") == repo_name for entry in data.get("optin_repos", [])):
            return True
    return False


def kill_onedrive() -> None:
    """Kill OneDrive.exe if running (GLOBAL-025). Skipped on exempt hosts."""
    if socket.gethostname().upper() in {"BLUEBERRY-MCP"}:
        return
    tasklist = _run(["tasklist", "/FI", "IMAGENAME eq OneDrive.exe"])
    if "OneDrive.exe" in tasklist:
        _run(["taskkill", "/F", "/IM", "OneDrive.exe"])
        print("OneDrive.exe killed (GLOBAL-025)")


def main(*, skip_ping: bool = False) -> int:
    repo_root = Path.cwd().resolve()

    # Ensure we are inside a git repo
    git_dir = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root)
    if git_dir:
        repo_root = Path(git_dir)

    print(f"session_guard: {repo_root.name}")
    print("-" * 40)

    # (f) Kill OneDrive first -- non-blocking
    kill_onedrive()

    # (a) Check rules -- BLOCKING if missing
    rules_missing = check_rules(repo_root)

    # (b) Check pings -- WARNING only (agent reads as first action)
    #     Pings cannot block session start: the session must START to
    #     read and acknowledge them.  The Stop hook (ping_check.py)
    #     still blocks finishing without acknowledging.
    has_unread = False
    if skip_ping:
        print("Ping check skipped (--no-ping).")
    else:
        has_unread = check_pings(repo_root)

    # (c) Uncommitted work -- warning only
    check_uncommitted(repo_root)

    # (d) Unpushed commits -- warning only
    check_unpushed(repo_root)

    # (e) Active branch -- warning only
    check_branch(repo_root)

    # (h) Behind remote -- ACTION REQUIRED if behind
    check_behind_remote(repo_root)

    # (i) Cross-repo state -- warns on any dirty / unpushed sibling repo
    check_cross_repo_state(repo_root)

    # (j) Memory mirror restore -- closes GLOBAL-030 cross-machine gap
    check_memory_mirror(repo_root)

    # (g) Stale artifacts -- warning with count
    stale_count = check_stale_artifacts(repo_root)

    # (k) Dispatch trigger -- pending controller dispatch
    has_dispatch = check_dispatch_trigger(repo_root)

    # (l) Exclusion violations -- re-added intentionally-removed items
    excl_violations = check_exclusion_violations(repo_root)
    for violation in excl_violations:
        print(f"WARNING: {violation}")

    print("-" * 40)
    if rules_missing:
        print("BLOCKED: Fix rule files before proceeding.")
        return 1

    if has_unread:
        print(
            "ACTION REQUIRED: Unread ping(s) detected. "
            "Run /upnote-protocol as your FIRST action this session."
        )

    if has_dispatch:
        print(
            "ACTION REQUIRED: Pending controller dispatch detected. "
            "Type 'controller dispatch' to execute."
        )

    if excl_violations:
        print(
            f"WARNING: {len(excl_violations)} exclusion violation(s) in settings.json. "
            "Review and remove the flagged hooks."
        )

    if stale_count > 0:
        print(f"Cleaned {stale_count} stale artifact(s) at session start.")

    # (m) Levi auto-ingest -- pull all new memories + reports into Levi at session start
    #     Runs silently; any failure is non-blocking (Levi is a learning aid, not a gate).
    _levi_auto_ingest(repo_root)

    print("Session guard passed.")
    return 0


def _levi_auto_ingest(repo_root: Path) -> None:
    """Silently ingest memories + reports into Leviathan at session start."""
    try:
        import subprocess as _sp
        # Memories: all repos' .claude/memory/
        r1 = _sp.run(
            [sys.executable, "-m", "src.main", "levi-sync", "--ingest"],
            cwd=repo_root, capture_output=True, text=True, timeout=60,
        )
        # Reports: NP_ClaudeAgent report/ + archive/
        r2 = _sp.run(
            [sys.executable, "-m", "src.main", "levi-sync", "--reports"],
            cwd=repo_root, capture_output=True, text=True, timeout=60,
        )
        # Surface summary line if anything new was ingested
        for r in (r1, r2):
            for line in r.stdout.splitlines():
                if "new" in line and not line.strip().startswith("0 new"):
                    print(f"Levi: {line.strip()}")
    except Exception:  # noqa: BLE001
        pass  # Never block session start due to Levi ingest failure


if __name__ == "__main__":
    skip = "--no-ping" in sys.argv
    sys.exit(main(skip_ping=skip))
