# Keynote-Suite — Controller Dispatch (CTRL-004)

> This file is managed by the NP_ClaudeAgent Controller. Project-level CLAUDE.md is at the repo root: `CLAUDE.md`.

## Controller Dispatch

> Dispatched by NP_ClaudeAgent Controller on 2026-04-24. Execute all items, commit with `[DISPATCH-DONE]` prefix, then notify Controller.

### Completed (2026-04-25)

All 5 dispatch tasks done by Controller (@vscode-ext):
- GROUND-001: baseline files committed
- GROUND-006: tools/.gitkeep created
- GLOBAL-009: Config & Settings Ownership table added to both CLAUDE.md files
- GLOBAL-011: .gitignore updated with standard patterns
- GLOBAL-029: all placeholder comments replaced with real content

## Project Goal

Bi-directional Dynamo automation engine for Civil 3D keynote callouts and tables.
Manages keynote definitions, callout placement, and table generation across Revit/Civil 3D projects.


## File Encoding

All source files: UTF-8, no BOM. See GLOBAL-002 in the global rules registry.


## Branch Naming

Follow GLOBAL-003: `main`, `feature/{topic}`, `fix/{topic}`, `claude/{topic}-dev{N}`.


## Completion Protocol

Before declaring any task complete:
1. Run the project test suite or verification script
2. Verify zero errors in output
3. If either fails, fix the issue. Do NOT mark done until all pass.




## Config & Settings Ownership

| File | Owner | Purpose |
|------|-------|---------|
| `UserPref.json` | Agent | User preferences for agent behavior |
| `.vscode/extensions.json` | Agent | Recommended VS Code extensions |
| `.gitattributes` | Agent | Line-ending and diff settings |
| `.gitignore` | Agent | Standard ignore patterns |
| `controller-note/.ping` | Controller | Unread signal |
| `controller-note/.last-read` | Agent | Read-acknowledgment timestamp |

## Safety Contract

- **Read-only:** All external Revit/Civil 3D project files, reference data
- **Writable:** This repo only (Keynote-Suite/) — keynote definitions, output scripts, reports


## Handoff Notes (last updated 2026-04-24)

### What was completed this session
- Baseline scaffolded by Controller (CTRL-004): CLAUDE.md, .gitignore, controller-note/

### What still needs work
- Core Dynamo scripts not yet built — pending Designer kickoff

### Known issues
- None active


## Controller-Note Protocol (CTRL-005)

### Session Start (BLOCKING)

Before ANY other work, check for unread pings:
1. Compare `controller-note/.ping` mtime vs `controller-note/.last-read` mtime
2. If `.ping` is newer  -  there is unread content
3. Announce to user: "New ping from controller  -  reading now"
4. Read `controller-note/controller-upnote.md`
5. Update `controller-note/.last-read`
6. Respond if needed

This is a BLOCKING prerequisite  -  no work until pings are checked.

### Mid-Session Re-Scan

After every major task (commit, baseline push, feature merge), re-check `.ping` before proceeding.

### On Change: Write Upnote + Ping

When making changes that affect cross-repo state:
1. Append entry to `controller-note/{repo_name}-upnote.md`
2. Touch `controller-note/.ping`


## Zero Hardcoding  -  Absolute Portability (GLOBAL-004)

NOTHING may be hardcoded. Every value that differs between machines, users, or environments MUST be resolved at runtime.

**Forbidden (hardcoded):**
- Drive letters (`D:\DevOps`, `C:\Users\name`)
- GitHub owner/repo strings in source code
- Executable paths (`C:\Program Files\...`)
- Issue numbers, port numbers, usernames
- Any absolute path that only works on one machine

**Required (portable):**
- `Path(__file__).resolve().parent` for script root
- `Path.home()` / `%USERPROFILE%` / `$HOME` for user dirs
- `shutil.which()` for executable discovery
- Environment variables (`REPOS_ROOT`, `GITHUB_OWNER`) for deployment-specific values
- Config files (`config/repos.json`) for project identity

**Why:** Hardcoding is a FATAL design flaw. One hardcoded path renders the entire repo useless on a different machine, for a different user, or in a different fork.


## Execution Directives (ENFORCED  -  not optional)

- **Hard loop:** Fix errors yourself  -  never return broken output to user. Loop: fix → verify → repeat until clean.
- **Verify after every change:** Run tests → check output → must be clean or loop back and fix.
- **No secrets in output:** PID + process name only. Never dump command lines. Never log tokens.
- **Rules first:** Cite GLOBAL/CTRL rules before any decision. Never fall back to generic AI instincts.
- **No half-checks:** If the analyzer doesn't catch a gap, add the check  -  then fix the gap  -  then verify again.


## Dev-Check Quality Gate (CTRL-007)

Before any milestone commit or PR merge, run a multi-persona quality review:
- Minimum 10 consecutive clean rounds to pass
- Covers: architecture, security, UX, performance, accessibility
- **Auto-fix loop:** Agent MUST fix all CRITICAL and HIGH findings automatically and re-run checks until 10 consecutive clean rounds. Do NOT return to user with fixable errors  -  fix them, re-check, repeat. Only escalate to user if a finding requires a design decision or external action.
- Log the dev-check result in `report/`


## Recognized Trigger Phrases (GLOBAL-024)

These phrases from the Designer execute immediately  -  no clarification needed:
- `dev-check` / `quality check`  -  run multi-persona quality review (CTRL-007)
- `logic-check` / `validate plan`  -  validate a proposed plan (CTRL-010)
- `check ping` / `check notes`  -  scan controller-note for unread pings
- `controller dispatch` / `check with controller`  -  read + execute pending tasks
- `session exit`  -  run exit checklist (commit/stash/upnote)


## HTML Projection (CTRL-006)

If this project produces HTML output, the controller can trigger a mirror
workflow to publish to a public GitHub Pages repo. The agent must:
- Ensure `Output/` or `docs/` contains the latest built HTML before launch
- Never include secrets, PII, or internal paths in public HTML
- Verify the public mirror after push (check GitHub Pages URL)


## Shift Handoff Protocol

Multiple agents (Claude CLI, Copilot, VS Code extension) may work in this repo across shifts.

### Entry (incoming agent)
1. Compare `controller-note/.ping` vs `.last-read` timestamps
2. If `.ping` is newer  -  read all upnote files before doing any work
3. Read the **Handoff Notes** section in `.claude/CLAUDE.md`

### Exit (outgoing agent)
1. Append session summary to `controller-note/{repo_name}-upnote.md` (newest at top)
2. Update **Handoff Notes** in `.claude/CLAUDE.md`
3. Touch both `.ping` and `.last-read` to current UTC
4. Commit + push `controller-note/` changes

### Agent tagging (MANDATORY)
Every upnote entry header MUST include an `@agent` tag:
```
## [YYYY-MM-DD HH:MM] Topic -- type @agent-name
```
Valid tags: `@claude-cli`, `@copilot`, `@vscode-ext`, `@remote-cli`, `@cloud`

### Discovery
- **Claude CLI:** auto-reads `.claude/CLAUDE.md`
- **Copilot:** reads `.github/copilot-instructions.md` (points here)
- **Controller:** CTRL-005 convention (`controller-note/`)


## Pre-Compaction Protocol (GLOBAL-030)

**Triggers** — when the Designer says any of these phrases, run ALL steps automatically without waiting to be asked:
`ready for compaction`, `prep for compaction`, `getting ready for compaction`

1. **Completion gate** — run all tests/verification; must pass
2. **Update handoff notes** — move current session to "What was completed", update "What still needs work"
3. **Write controller-note upnote** — append session summary to `controller-note/{repo_name}-upnote.md` + touch `.ping` and `.last-read`
4. **Save memories** — write new feedback/project/reference `.md` files + update MEMORY.md index
5. **Mirror memories** — copy all new/changed memory files to `controller-note/agent-memory/` (GLOBAL-030)
6. **Commit + push** — single commit with `chore(compaction-prep): ...` message covering all docs
7. **Confirm** — print "Ready for compaction. All docs committed and pushed."

**PreCompact hook:** `pre_compact_capture.py` fires automatically when the context window is near full — scans the transcript for discovery signals ("add to baseline", "make that global", etc.) and writes verbatim snippets to `report/candidate_rules.md` so no insight is lost to compaction.


## Identity & Path Resolution (GLOBAL-031)

Folder names embedded in absolute paths are NOT a signal of the current user. On host machines running persistent services, the dev root may live under a service-account profile while the interactive user is different. Always resolve identity at runtime:

| Platform | Resolve via |
|----------|------------|
| PowerShell | `$env:USERPROFILE`, `$env:USERNAME` |
| Python | `os.environ.get('USERPROFILE')` / `Path.home()` |
| POSIX | `$HOME`, `$USER` |

Never state identity facts from a path string alone  -  verify with a runtime call.


## Memory Persistence Protocol (GLOBAL-030)

The Claude Code auto-memory folder (under `~/.claude/projects/...`) is local to one OS profile on one machine. Without a mirror, every feedback / project / reference / user memory is lost on machine swap, fresh clone, or profile reset.

**Mirror folder:** `controller-note/agent-memory/` (git-tracked, 1:1 with auto-memory). The mirror has its own `README.md` with restore steps.

**Three-tier memory model:**

| Tier | Location | Persistence |
|------|----------|-------------|
| Auto-memory | `~/.claude/projects/<slug>/memory/` | Local to one profile -- volatile |
| Mirror | `controller-note/agent-memory/` | Git-tracked -- survives machine swap |
| Canonical | `memories/` (curated) | Git-tracked -- deliberately maintained facts |

**Enforcement:**
- `memory_mirror.py` (PostToolUse) -- copies every auto-memory Write/Edit into the mirror.
- `session_guard.py` (SessionStart) -- restores mirror-only files into auto-memory at session start; MEMORY.md divergence logged as WARNING, never auto-overwritten.
- During `prep for compaction`: mirror all new/changed memories into `controller-note/agent-memory/` before commit.

**Anti-pattern:** Relying on `~/.claude/.../memory/` alone for anything that must survive a machine change. Always check the mirror for the authoritative copy.


## Stale & Archive Protocol

Stale items rot quietly. Every repo follows the same archival rules
so audits stay consistent across the ecosystem.

**Local artifacts** (build droppings, editor backups):
- Patterns: `*.bak`, `*.old`, `*.orig`, `*.tmp`, `*~`, `*.copy`, `*.rej`, `__pycache__/`, `*.pyc`
- Auto-cleaned at session start by `tools/session_guard.py`
- Auto-cleaned before commit by `.claude/hooks/pre_commit_guard.py`
- Never commit these. If a tool produces one, fix the tool to clean up.

**Stale branches** (> 30 days without commit, non-main):
- Flagged by CTRL-001 Harvest (INSP-003) in Controller audits
- Archive before delete: rename to `archive/{branch-name}` and push the rename so the history survives, then delete the original locally
- Pinned-on-purpose branches MUST have a PROTECT note in the upnote and a memory entry explaining why

**Retired rules / hooks / workflows**:
- Add a tombstone entry to `controller-note/exclusions.json` with reason + date + scope (the Controller's snapshot is mirrored here)
- Removed items MUST NOT be silently re-added by audit agents
- `session_guard.py` audits `.claude/settings.json` against exclusions at every session start and warns on violations

**Old reports / output files**:
- One-shot reports older than the current release land in `report/_archive/{YYYY-MM}/`
- Personal scratch output (cut lists, sketches) lives in `output/` but is removed before any compaction/PR

**Anti-pattern:** Deleting without a tombstone. The next agent will look at the gap, decide it's a bug, and re-create the problem.


## Exclusions Registry (CTRL-004 Tombstone Protocol)

`controller-note/exclusions.json` is a mirror of the Controller's
intentional-divergence registry. Every entry documents something
that was deliberately removed from this repo and MUST NOT be re-added.

**Schema:**
```
{
  "item_type": "hook | section | tool | workflow",
  "name": "file or section name",
  "scope": ["repo-A", "repo-B"]  // or "*" for all,
  "reason": "why removed",
  "removed_date": "YYYY-MM-DD"
}
```

**Before adding anything that looks 'missing':** check this file
first. If the missing item is listed, it was removed on purpose --
do not re-add it. Discuss with the Designer if the removal needs to
be revisited.

`session_guard.py` runs `audit_settings()` at every session start and
warns if `.claude/settings.json` references a tombstoned item.


## Pre-Compaction Levi Push (CTRL-011 / Lane B)

Extends the Pre-Compaction Protocol with a terminal step: push
the git-tracked memory mirror into Leviathan so memories survive
beyond compaction, machine swap, AND fresh-clone scenarios.

**When:** runs AFTER the commit + push step. Levi mirrors
git-committed truth, never WIP.

**How:** `py tools/levi_push.py` walks `controller-note/agent-memory/` and appends one JSONL line per
memory file to `controller-note/levi_inbound/YYYY-MM-DD.jsonl`.
The Controller drains queues into Leviathan during repo-sync.

**Why queue-and-drain instead of direct push:** decouples agent
from Levi MCP availability (queues survive Levi downtime), and
agents do not need to know Levi's local path or auth.

**Trigger phrases that fire the full chain (existing + this step):**
- `ready for compaction`
- `prep for compaction`
- `getting ready for compaction`

See `reference/self_improve_v2_design.md` Lane B for the full
design and rationale.


## Just-Act Permissions (no permission prompts)

The Designer has pre-authorized every read/write/run tool inside the Safety Contract. To stop Claude Code from interrupting work with permission prompts, `.claude/settings.json` carries this allowlist as part of the controller baseline:

```json
"permissions": {
  "allow": [
    "Bash(*)", "Read(*)", "Write(*)", "Edit(*)",
    "Glob(*)", "Grep(*)", "WebFetch(*)", "WebSearch(*)",
    "mcp__*", "Agent(*)", "Task(*)"
  ]
}
```

**Rules:**
- The Controller (CTRL-004) backfills any missing entry on every baseline push. Removing an entry locally is not durable -- the next sync restores it.
- If a project truly needs to opt out of a single permission, add a tombstone to `config/exclusions.json` with `type: "permission"` and `identifier: "<entry>"`. The Controller will then skip that one entry for this repo while keeping the others.
- Extra project-specific entries (e.g. `PowerShell(*)` on a Windows-only repo) are preserved; the backfill only ADDS, never removes.
- This is enforcement, not policy. The corresponding prose rule is the **Just act** bullet under Execution Directives.

