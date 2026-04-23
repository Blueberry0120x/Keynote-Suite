"""compact_reinject.py -- SessionStart hook (compact matcher): re-inject
critical context after context compaction.

When Claude's context window fills and compaction triggers, important details
from CLAUDE.md, handoff notes, and rules can be lost.  This hook fires on
the 'compact' SessionStart event and prints key reminders to stdout, which
Claude Code injects back into context.

Per Anthropic best practice: https://code.claude.com/docs/en/hooks-guide
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    project_dir = Path(hook_input.get("cwd", "."))

    # Build re-injection context from key sources
    parts: list[str] = [
        "=== POST-COMPACTION CONTEXT RE-INJECTION ===",
        "",
        "## Critical Rules (from CLAUDE.md)",
        "- Run `py tools/completion_gate.py` before declaring done",
        "- Cite GLOBAL/CTRL rules before any decision",
        "- pathlib.Path for all file ops, never os.path",
        "- Absolute imports only: `from src.models import Rule`",
        "- `from __future__ import annotations` in every module",
        "- 4 spaces, PEP 8, f-strings, lines under 100 chars",
        "",
        "## Safety Contract",
        "- Writable: NP_ClaudeAgent/ only (own repo)",
        "- Scoped writes to other repos: controller-note/, .claude/,"
        " baseline CLAUDE.md sections only",
        "- assert_write_scope() enforces this at runtime",
        "",
        "## Pipeline: Scanner > Extractor > Comparator > Refiner"
        " > Consolidator",
        "## 7 Orchestras: Repo-Sync, Controller-Note, Git-Projection,"
        " Dev-Check, Remote-Invoke, Note-Verify, Logic-Check, Log-Chat",
        "",
    ]

    # Inject recent git log for working context
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=str(project_dir),
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts.append("## Recent commits")
            parts.append(result.stdout.strip())
            parts.append("")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Inject handoff "what still needs work" if available
    claude_md = project_dir / ".claude" / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text(encoding="utf-8")
            # Extract "What still needs work" section
            start = content.find("### What still needs work")
            if start >= 0:
                end = content.find("\n### ", start + 1)
                snippet = content[start:end] if end > 0 else content[start:]
                parts.append(snippet.strip())
                parts.append("")
        except OSError:
            pass

    parts.append("=== END RE-INJECTION ===")
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
