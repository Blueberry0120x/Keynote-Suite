"""
failure_analyze.py -- Self-learning failure documentation + recursive why-chain analysis.


Usage:
    py tools/failure_analyze.py --failure "PowerShell tool exits 1 on all commands"
    py tools/failure_analyze.py --list
    py tools/failure_analyze.py --summary

Every failure gets a dated entry in report/failure_log.md with:
  - What failed
  - Recursive why-chain (why -> why -> root cause)
  - Fix applied
  - Prevention rule (feeds back to memory)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 stdout so non-ASCII characters in log paths don't crash on Windows CP1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT    = Path(__file__).resolve().parent.parent
LOG     = ROOT / "report" / "failure_log.md"
MEM_DIR = Path.home() / ".claude" / "projects"
MIRROR  = ROOT / "controller-note" / "agent-memory"

# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _date() -> str:
    return datetime.now().strftime("%Y%m%d")


def append_failure(
    *,
    what: str,
    why_chain: list[str],
    fix: str,
    prevention: str,
    category: str = "tooling",
) -> Path:
    """Append a structured failure entry to report/failure_log.md."""
    LOG.parent.mkdir(parents=True, exist_ok=True)

    header = f"\n## [{_timestamp()}] {what[:80]}\n"
    body_lines = [
        f"**Category:** {category}\n",
        "**Why-chain (recursive root-cause):**\n",
    ]
    for i, why in enumerate(why_chain, 1):
        body_lines.append(f"{i}. {why}")
    body_lines += [
        "",
        f"**Fix applied:** {fix}",
        "",
        f"**Prevention rule:** {prevention}",
        "",
        "---",
    ]

    entry = header + "\n".join(body_lines) + "\n"

    if not LOG.exists():
        LOG.write_text(
            "# Failure Log — NP_ClaudeAgent\n\n"
            "Recursive why-chain analysis for every tool/agent failure.\n"
            "Each entry feeds back as a self-learning memory.\n\n",
            encoding="utf-8",
        )

    with LOG.open("a", encoding="utf-8") as f:
        f.write(entry)

    print(f"[OK] Failure logged -> {LOG}")
    return LOG


def _write_memory(slug: str, content: str) -> None:
    """Write a feedback memory entry to auto-memory + mirror."""
    # Find auto-memory folder (search for projects/<hash>/memory/)
    candidates: list[Path] = []
    if MEM_DIR.exists():
        for proj in MEM_DIR.iterdir():
            mem = proj / "memory"
            if mem.is_dir():
                candidates.append(mem)

    mem_content = (
        f"---\n"
        f"name: {slug}\n"
        f"description: {content.splitlines()[0][:100]}\n"
        f"metadata:\n"
        f"  type: feedback\n"
        f"---\n\n"
        f"{content}\n"
    )

    written: list[Path] = []
    for mem_dir in candidates:
        target = mem_dir / f"{slug}.md"
        target.write_text(mem_content, encoding="utf-8")
        written.append(target)

    # Mirror
    if MIRROR.exists():
        mirror_target = MIRROR / f"{slug}.md"
        mirror_target.write_text(mem_content, encoding="utf-8")
        written.append(mirror_target)

    if written:
        print(f"[OK] Memory written to {len(written)} location(s)")
    else:
        print("[WARN] No auto-memory directory found -- memory not saved")

    # Auto-ingest into Leviathan so failures are searchable in Levi immediately
    try:
        import subprocess
        result = subprocess.run(
            ["py", "-m", "src.main", "levi-sync", "--ingest"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        if result.returncode == 0:
            summary_line = [ln for ln in result.stdout.splitlines() if "new" in ln]
            print(f"[OK] Levi ingest: {summary_line[0].strip() if summary_line else 'done'}")
        else:
            print(f"[WARN] Levi ingest failed (exit {result.returncode})")
    except Exception as exc:
        print(f"[WARN] Levi ingest skipped: {exc}")


def list_failures() -> None:
    if not LOG.exists():
        print("No failures logged yet.")
        return
    text = LOG.read_text(encoding="utf-8")
    entries = re.findall(r"^## \[.*", text, re.MULTILINE)
    print(f"Failure log: {LOG}")
    print(f"Total entries: {len(entries)}\n")
    for e in entries:
        print(" ", e)


def summary() -> None:
    if not LOG.exists():
        print("No failures logged yet.")
        return
    text = LOG.read_text(encoding="utf-8")
    categories = re.findall(r"\*\*Category:\*\* (\S+)", text)
    from collections import Counter
    counts = Counter(categories)
    print("Failure summary by category:")
    for cat, n in counts.most_common():
        print(f"  {cat:20s} {n}")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Self-learning failure documentation")
    ap.add_argument("--failure", help="One-line description of what failed")
    ap.add_argument("--why", nargs="+", help="Recursive why-chain items (ordered)")
    ap.add_argument("--fix", help="Fix that was applied")
    ap.add_argument("--prevention", help="Rule to prevent recurrence")
    ap.add_argument("--category", default="tooling",
                    help="Category: tooling | agent-behavior | build | test | protocol")
    ap.add_argument("--save-memory", action="store_true",
                    help="Also write a feedback memory entry")
    ap.add_argument("--memory-slug", help="Memory filename slug (no .md)")
    ap.add_argument("--list", action="store_true", help="List logged failures")
    ap.add_argument("--summary", action="store_true", help="Failure summary by category")
    args = ap.parse_args()

    if args.list:
        list_failures()
        return
    if args.summary:
        summary()
        return

    if not args.failure:
        ap.print_help()
        sys.exit(1)

    why_chain = args.why or ["(not provided)"]
    fix = args.fix or "(not provided)"
    prevention = args.prevention or "(not provided)"

    append_failure(
        what=args.failure,
        why_chain=why_chain,
        fix=fix,
        prevention=prevention,
        category=args.category,
    )

    if args.save_memory and args.memory_slug:
        mem_body = (
            f"{prevention}\n\n"
            f"**Why:** {why_chain[-1]} (see failure_log.md [{_timestamp()}])\n\n"
            f"**How to apply:** {fix}"
        )
        _write_memory(args.memory_slug, mem_body)


if __name__ == "__main__":
    main()
