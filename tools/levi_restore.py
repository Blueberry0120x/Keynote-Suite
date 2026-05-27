"""levi_restore.py -- cold-storage memory restore from Leviathan.

Closes the last leg of the memory triangle:
  - auto-memory (~/.claude/...) ........ volatile, machine-local
  - mirror (controller-note/agent-memory) git-tracked, durable
  - Leviathan SQLite ................... cold storage, semantic search

Use cases:
  1. `controller-note/agent-memory/` got accidentally deleted in a repo.
     Run `levi_restore.py --repo <name>` to rebuild from Levi.
  2. After accidentally `git rm -r` on the mirror folder and pushing it.
     Run on the controller machine which still has Levi populated.

NOT a cross-machine restore. Levi's SQLite is `.gitignore`d -- the db
does not travel between machines via git pull. For cross-machine
portability of Levi state, see `tools/levi_export.py` which emits a
git-tracked JSONL snapshot.

Lookups query Leviathan directly via sqlite3 (no dependency on the
Leviathan Python package). Convention from Leviathan's `ingest-memories`
command:
  wing  = "agent-memory"
  room  = <repo_name>
  source_path = absolute path on the machine that ingested
  chunk_index = order within source file
  content     = verbatim chunk content

Restore reconstructs original files by grouping rows by source_path,
ordering by chunk_index, concatenating content, and writing the result
to the destination repo's `controller-note/agent-memory/<basename>`.

Usage:
  py tools/levi_restore.py --repo NP_ClaudeAgent              # restore one repo
  py tools/levi_restore.py --all                              # all active repos
  py tools/levi_restore.py --repo Levi --dry-run              # preview only
  py tools/levi_restore.py --repo Levi --force                # overwrite existing
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LOCAL_REPOS = ROOT / "config" / "local_repos.json"


def _levi_db_path() -> Path | None:
    """Resolve Leviathan SQLite path. Returns None if unfindable."""
    env = os.environ.get("LEVIATHAN_STORE")
    if env:
        p = Path(env)
        if p.exists():
            return p
    # Default: sibling-repo Leviathan/leviathan.db
    repos_root = Path(os.environ.get("REPOS_ROOT") or str(ROOT.parent))
    candidate = repos_root / "Leviathan" / "leviathan.db"
    if candidate.exists():
        return candidate
    return None


def _load_local_repos() -> dict[str, Path]:
    if not LOCAL_REPOS.exists():
        return {}
    try:
        data = json.loads(LOCAL_REPOS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, Path] = {}
    for name, path_str in (data.get("repos") or {}).items():
        if isinstance(path_str, str):
            p = Path(path_str)
            if p.exists():
                out[name] = p
    return out


def restore_repo(
    repo_name: str,
    repo_path: Path,
    db_path: Path,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[int, int, list[str]]:
    """Restore one repo's memory mirror from Leviathan.

    Returns (files_restored, files_skipped, errors).
    """
    errors: list[str] = []
    dest_dir = repo_path / "controller-note" / "agent-memory"

    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return (0, 0, [f"open {db_path}: {exc}"])

    try:
        cur = con.execute(
            "SELECT source_path, chunk_index, content "
            "FROM drawers WHERE wing='agent-memory' AND room=? "
            "ORDER BY source_path, chunk_index",
            (repo_name,),
        )
        rows = cur.fetchall()
    except sqlite3.Error as exc:
        con.close()
        return (0, 0, [f"query: {exc}"])
    finally:
        con.close()

    if not rows:
        return (0, 0, [f"no Leviathan chunks for room={repo_name}"])

    # Group chunks by source_path, ordered already by chunk_index
    by_source: dict[str, list[str]] = {}
    for row in rows:
        by_source.setdefault(row["source_path"], []).append(row["content"])

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    restored = 0
    skipped = 0
    for source_path, chunks in by_source.items():
        # Normalize basename -- the original may have been from a different
        # absolute path (different machine) so we only trust the filename.
        basename = Path(source_path).name
        if not basename or not basename.endswith(".md"):
            continue
        dest = dest_dir / basename

        # If destination already exists and not forcing, skip
        if dest.exists() and not force:
            skipped += 1
            continue

        content = "".join(chunks)
        if dry_run:
            print(f"  would restore {basename} ({len(chunks)} chunks, {len(content)} chars)")
        else:
            try:
                dest.write_text(content, encoding="utf-8")
            except OSError as exc:
                errors.append(f"write {basename}: {exc}")
                continue
        restored += 1

    return (restored, skipped, errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", help="Restore this repo (e.g. NP_ClaudeAgent)")
    parser.add_argument(
        "--all", action="store_true",
        help="Restore every active repo in config/local_repos.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be restored without writing",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing mirror files",
    )
    parser.add_argument(
        "--db", help="Path to Leviathan SQLite (overrides LEVIATHAN_STORE env)",
    )
    args = parser.parse_args()

    if not args.repo and not args.all:
        parser.error("specify --repo NAME or --all")

    db_path = Path(args.db) if args.db else _levi_db_path()
    if db_path is None or not db_path.exists():
        print(
            "ERROR: Leviathan SQLite not found. Set LEVIATHAN_STORE or "
            "ensure Leviathan/leviathan.db exists sibling to this repo.",
            file=sys.stderr,
        )
        print(
            "(Levi DB is gitignored; on a fresh machine populate it with "
            "`leviathan ingest-memories` from the Leviathan repo.)",
            file=sys.stderr,
        )
        return 2

    repos = _load_local_repos()
    if args.all:
        targets = repos
    else:
        if args.repo not in repos:
            # Try partial match
            matches = {k: v for k, v in repos.items() if args.repo.lower() in k.lower()}
            if len(matches) == 1:
                name, path = next(iter(matches.items()))
                targets = {name: path}
            else:
                print(f"ERROR: repo {args.repo!r} not in config/local_repos.json", file=sys.stderr)
                return 2
        else:
            targets = {args.repo: repos[args.repo]}

    print(f"Levi restore from {db_path} (dry_run={args.dry_run}, force={args.force})")
    print("-" * 70)

    total_restored = total_skipped = total_errors = 0
    for name, path in targets.items():
        print(f"[{name}] -> {path / 'controller-note' / 'agent-memory'}")
        restored, skipped, errors = restore_repo(
            name, path, db_path, dry_run=args.dry_run, force=args.force,
        )
        print(f"  restored={restored} skipped={skipped} errors={len(errors)}")
        for err in errors:
            print(f"  ERROR: {err}")
        total_restored += restored
        total_skipped += skipped
        total_errors += len(errors)

    print("-" * 70)
    print(
        f"TOTAL: {total_restored} restored, {total_skipped} skipped, "
        f"{total_errors} errors across {len(targets)} repo(s)"
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
