"""pre_compact_capture.py — PreCompact hook: write raw discoveries verbatim to
report/candidate_rules.md before context is compacted (GLOBAL-030).

Fires automatically when Claude Code detects the context window is near full.
Scans the last 50 transcript messages for discovery signals — phrases that
indicate a new rule, pattern, or baseline improvement was discussed.
Writes matching snippets verbatim so no cross-repo insight is lost to compaction.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# User phrases that signal a new rule or baseline improvement was discussed
_USER_SIGNALS = [
    "that should be in our baseline",
    "add to baseline",
    "add as a rule",
    "make that global",
    "add to global rules",
    "should be global",
    "new global rule",
    "promote to global",
    "should be a global",
    "add to global_rules",
    "make it a rule",
    "put that in the baseline",
    "add that globally",
]

# Assistant phrases that indicate a rule candidate was proposed
_ASSISTANT_SIGNALS = [
    "candidate rule",
    "add to global_rules",
    "promote to global",
    "new global rule",
    "GLOBAL-030",
    "GLOBAL-031",
    "GLOBAL-032",
    "GLOBAL-033",
    "GLOBAL-034",
    "GLOBAL-035",
    "should be in our baseline",
    "baseline standard",
    "Path B — build auto-discovery",
]

_SCAN_TAIL = 60  # how many recent messages to check
_SNIPPET_BEFORE = 120  # chars of context before signal
_SNIPPET_AFTER = 500  # chars of context after signal


def _read_transcript(transcript_path: str) -> list[dict]:
    path = Path(transcript_path)
    if not path.exists():
        return []
    messages: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return messages


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                for item in block.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
        return "\n".join(parts)
    return str(content)


def _find_discoveries(messages: list[dict]) -> list[tuple[str, str, str]]:
    """Return list of (role, verbatim_snippet, matched_signal)."""
    found: list[tuple[str, str, str]] = []
    seen_signals: set[str] = set()
    recent = messages[-_SCAN_TAIL:]

    for msg in recent:
        role = msg.get("role", "")
        text = _extract_text(msg.get("content", ""))
        lower = text.lower()

        signals = _USER_SIGNALS if role == "human" else _ASSISTANT_SIGNALS
        for signal in signals:
            if signal.lower() in lower and signal not in seen_signals:
                idx = lower.find(signal.lower())
                start = max(0, idx - _SNIPPET_BEFORE)
                end = min(len(text), idx + _SNIPPET_AFTER)
                snippet = text[start:end].strip()
                found.append((role, snippet, signal))
                seen_signals.add(signal)
                break  # one signal per message

    return found


def _append_to_candidate_rules(path: Path, entries: list[str]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n".join(entries)

    # Insert after the last --- divider (newest at top of entries section)
    insert_at = existing.rfind("\n---\n")
    if insert_at >= 0:
        new_content = existing[: insert_at + 5] + block + existing[insert_at + 5 :]
    else:
        new_content = existing + "\n" + block

    path.write_text(new_content, encoding="utf-8")


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    transcript_path = hook_input.get("transcript_path", "")
    cwd = Path(hook_input.get("cwd", "."))
    candidate_path = cwd / "report" / "candidate_rules.md"

    if not candidate_path.parent.exists():
        return 0  # not our repo structure

    if not transcript_path:
        return 0

    messages = _read_transcript(transcript_path)
    if not messages:
        return 0

    discoveries = _find_discoveries(messages)
    if not discoveries:
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries = [
        f"\n## [{now}] Pre-compaction capture — {len(discoveries)} signal(s)\n",
    ]
    for role, snippet, signal in discoveries:
        entries.append(f"**Signal:** `{signal}` | **Role:** {role}\n")
        entries.append(f"```\n{snippet}\n```\n")

    _append_to_candidate_rules(candidate_path, entries)

    print(
        f"[GLOBAL-030] PreCompact: captured {len(discoveries)} discovery signal(s)"
        f" → report/candidate_rules.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
