"""levi_push.py -- Pre-compaction memory push to Leviathan (CTRL-011 + GLOBAL-030).

Walks this repo's git-tracked controller-note/agent-memory/ mirror and
appends a JSONL inbound queue entry for each .md file at
controller-note/levi_inbound/YYYY-MM-DD.jsonl. The Controller drains
these queues into Leviathan during repo-sync.

Why queue-and-drain instead of direct Levi push:
  - Decouples agent from Levi MCP availability (queues survive Levi downtime).
  - Project agent does not need to know Levi's local path or auth.
  - Drain is idempotent (content-hash de-dup on Levi side).
  - Queue files are git-tracked, so the push survives machine swap.

Usage:
  py tools/levi_push.py                  # walk + queue, prints summary
  py tools/levi_push.py --dry-run        # walk only, no writes
  py tools/levi_push.py --since 2026-05-20  # only files modified after date

Exit codes:
  0 = success (or nothing-to-do)
  1 = unrecoverable error (mirror missing, queue dir uncreatable)

See reference/observation_infrastructure_v2.md section 3 (Lane B).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path.cwd().resolve()
MIRROR_DIR = REPO_ROOT / "controller-note" / "agent-memory"
QUEUE_DIR = REPO_ROOT / "controller-note" / "levi_inbound"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _walk_mirror(since: datetime | None) -> Iterable[Path]:
    """Yield .md files under the mirror, optionally filtered by mtime."""
    if not MIRROR_DIR.exists():
        return
    for p in MIRROR_DIR.rglob("*.md"):
        if not p.is_file():
            continue
        if since is not None:
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if mtime < since:
                continue
        yield p


def _content_hash(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()[:16]


def _payload_summary(path: Path) -> str:
    """First 400 chars of the file -- enough for Levi to classify."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:400]


def queue_push(dry_run: bool, since: datetime | None) -> int:
    if not MIRROR_DIR.exists():
        print(f"[levi_push] no mirror at {MIRROR_DIR} -- nothing to push.")
        return 0

    repo_name = REPO_ROOT.name
    entries: list[dict] = []

    for p in _walk_mirror(since):
        rel = p.relative_to(REPO_ROOT)
        entries.append({
            "ts": _iso_now(),
            "source_repo": repo_name,
            "source_path": str(rel).replace("\\", "/"),
            "content_hash": _content_hash(p),
            "payload_preview": _payload_summary(p),
        })

    if not entries:
        print(f"[levi_push] {repo_name}: 0 files to queue.")
        return 0

    if dry_run:
        print(
            f"[levi_push] {repo_name}: would queue {len(entries)} file(s) "
            f"to controller-note/levi_inbound/{_date_str()}.jsonl"
        )
        return 0

    try:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[levi_push] cannot create queue dir: {exc}", file=sys.stderr)
        return 1

    queue_file = QUEUE_DIR / f"{_date_str()}.jsonl"
    try:
        with queue_file.open("a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[levi_push] write failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"[levi_push] {repo_name}: queued {len(entries)} file(s) -> "
        f"controller-note/levi_inbound/{_date_str()}.jsonl"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO date (YYYY-MM-DD); only queue files modified after this date",
    )
    args = parser.parse_args()

    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"[levi_push] invalid --since: {args.since}", file=sys.stderr)
            return 1

    return queue_push(dry_run=args.dry_run, since=since)


if __name__ == "__main__":
    sys.exit(main())
