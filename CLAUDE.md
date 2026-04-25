# Keynote-Suite

## Project Goal

Bi-directional Dynamo automation engine for Civil 3D keynote callouts and tables.
Manages keynote definitions, callout placement, and table generation across Revit/Civil 3D projects.
Built for AU 2026 presentation and production use.


## File Encoding

All source files: UTF-8, no BOM. See GLOBAL-002 in the global rules registry.


## Branch Naming

Follow GLOBAL-003: `main`, `feature/{topic}`, `fix/{topic}`, `claude/{topic}-dev{N}`.


## Completion Protocol

Before declaring any task complete:
1. Run the project test suite or verification script
2. Verify zero errors in output
3. If either fails, fix the issue. Do NOT mark done until all pass.


## Safety Contract

- **Read-only:** All external Revit/Civil 3D project files, reference data
- **Writable:** This repo only (Keynote-Suite/) — keynote definitions, output scripts, reports


## Handoff Notes (last updated 2026-04-23)

### What was completed this session
- Baseline scaffolded by Controller (CTRL-004): CLAUDE.md, .gitignore, .gitattributes, controller-note/, reference/, report/

### What still needs work
- Core Dynamo scripts not yet built — pending Designer kickoff

### Known issues
- None active




## Config & Settings Ownership

| File | Owner | Purpose |
|------|-------|---------|
| `UserPref.json` | Agent | User preferences for Keynote-Suite agent behavior |
| `.vscode/extensions.json` | Agent | Recommended VS Code extensions |
| `.gitattributes` | Agent | Line-ending and diff settings |
| `.gitignore` | Agent | Standard ignore patterns |
| `controller-note/.ping` | Controller | Unread signal |
| `controller-note/.last-read` | Agent | Read-acknowledgment timestamp |

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

