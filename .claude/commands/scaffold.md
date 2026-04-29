# /scaffold -- Enforce uniform folder structure across all repos
> Called as step 3 of `/push-baseline`. Run standalone for structure-only fixes.

Ensures every repo has the standard core directories and files.
Creates missing items. Renames case-mismatched folders.

## Canonical folder structure (MANDATORY for all repos)

```
{repo}/
  .claude/
    CLAUDE.md           # Project rules (primary location)
    hooks/              # Enforcement hooks (from baseline)
    settings.json       # Hook configuration
  .gitignore            # Standard patterns (GLOBAL-011)
  controller-note/      # Upnotes, pings (CTRL-005)
    .ping
    .last-read
  reference/            # Docs + best practices (GLOBAL-019)
    best-practices/     # Synced by CTRL-004 (read-only)
      hooks-baseline/   # Portable hooks + VERSION
  report/               # Reports, analysis output (GLOBAL-005) -- LOWERCASE
  tools/                # Scripts, guards, utilities
    session_guard_lite.py  # Session guard (from baseline)
  UserPref.json         # User preferences (GLOBAL-016)
```

## Project-specific additions (allowed, not enforced)
- `src/`, `config/`, `tests/` -- Python projects
- `Engine/`, `Projects/`, `Modules/` -- PowerShell projects
- `bin/`, `obj/` -- C#/.NET projects
- `data/`, `input/`, `output/` -- Data pipeline projects
- `docs/` -- Additional documentation

## Steps

1. For each active repo in `config/local_repos.json`:
   a. Check each canonical folder/file exists
   b. Fix case mismatches: `Report/` -> `report/`, `REPORT/` -> `report/`, etc.
      (use git mv for tracked dirs to preserve history)
   c. Create missing canonical dirs with `.gitkeep` if empty
   d. Report what was created/renamed
2. For read-only repos: dispatch the changes via controller-note + ping
3. Run GROUND-006 check to verify

## Rules
- NEVER delete project-specific folders
- NEVER rename project-specific folders (only canonical ones)
- Case fixes use `git mv` to preserve history
- New dirs get `.gitkeep` so git tracks them
