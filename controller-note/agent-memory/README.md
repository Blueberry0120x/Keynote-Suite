# Agent Memory Snapshot (git-tracked mirror)

This directory mirrors the contents of the Claude Code auto-memory folder for
this project, which by default lives outside the repo at:

```
%USERPROFILE%\.claude\projects\d--DevOps-Keynote-Suite\memory\
```

That path is **local to one Windows profile on one machine**. Without this
mirror, all auto-memory (feedback, project, reference, user entries) is lost
when the user switches machines, reinstalls, or clones the repo fresh.

## Why this exists

After the 2026-05-16 Master-ProjectLibrary Harbor incident — where 2 hours
of Designer work was at risk because auto-memory only lived at
`~/.claude/projects/.../memory/` — the Controller deployed a baseline rule:
**every active repo must mirror its auto-memory into git**. This folder is
that mirror. A `memory_mirror.py` PostToolUse hook keeps it in sync
automatically; this README documents the contract for humans.

## Contract

- Auto-memory folder is the **authoritative source** — Claude writes there first.
- This folder is the **persisted snapshot** — 1:1 with auto-memory, committed.
- After ANY add/update/delete in auto-memory, the change is mirrored here
  by the `memory_mirror.py` PostToolUse hook (automatic).
- `MEMORY.md` (the index) is mirrored verbatim.
- The `chat-history/` subfolder is mirrored too.
- File names match the auto-memory file names 1:1.

## Restore procedure (new machine)

```bash
DST="$HOME/.claude/projects/d--DevOps-Keynote-Suite/memory"
mkdir -p "$DST/chat-history"
cp controller-note/agent-memory/*.md "$DST/" 2>/dev/null
cp controller-note/agent-memory/chat-history/*.md "$DST/chat-history/" 2>/dev/null
```

After restore, the next Claude Code session will read `MEMORY.md` as part
of its standard auto-memory load and have full prior context.

## See also

- Project rule: `.claude/CLAUDE.md` → "Memory Persistence Protocol" section
- Global rule: `report/global_rules.md` → GLOBAL-030 Memory Persistence
