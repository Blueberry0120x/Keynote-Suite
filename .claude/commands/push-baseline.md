# /push-baseline — Deploy Full Baseline + Verify Rules & Memory

Push the complete baseline (hooks, skills, settings, rules) to all active repos,
then verify that rules and memory are consistent.

## Chain (runs in sequence)

1. **Sync hooks** → deploy latest hooks from `reference/best-practices/hooks-baseline/`
2. **Deploy settings.json.template** → merge into each repo's `.claude/settings.json`
3. **Deploy skills** → copy `.claude/commands/*.md` to all repos
4. **Verify rules** → check each repo's CLAUDE.md contains required baseline sections
5. **Check memory consistency** → scan for stale/contradicted memory entries
6. **Check pings** → scan all repos for unread pings (CTRL-005)
7. **Report** → summary table of what was deployed, what passed, what needs attention

## Hooks Deployment (formerly /sync-hooks + /baseline)

1. Read `config/hook_registry.json` for the rule-to-hook mapping
2. Read `reference/best-practices/hooks-baseline/VERSION` for canonical version
3. Read `config/local_repos.json` for all active repo paths
4. For each active repo:
   a. Check `{repo}/reference/best-practices/hooks-baseline/VERSION`
   b. If missing or outdated:
      - Ensure `.claude/hooks/` dir exists — create if not
      - Ensure `tools/` dir exists — create if not
      - Copy ALL portable hooks from baseline to `{repo}/.claude/hooks/`
      - Copy `session_guard_lite.py` to `{repo}/tools/`
      - Copy `VERSION` to `{repo}/reference/best-practices/hooks-baseline/`
      - Merge `settings.json.template` into `{repo}/.claude/settings.json`
        (ADD new hooks, preserve existing entries, never overwrite)
      - Write dispatch note: "[HOOKS-UPDATE] Baseline v{N} deployed"
      - Touch `.ping`
   c. If current: skip, report "up to date"
5. Report summary table: repo, old version, new version, status

## Verification Steps

1. For each active repo in `config/repos.json`:
   - Verify `CLAUDE.md` has XPLAT-001 architecture rule
   - Verify `.claude/settings.json` has xplat_guard hook
   - Verify `tests/test_xplat_guard.py` exists (for repos with `src/`)
2. Run `/check-pings` to catch any unread notifications
3. Report results

## Rules
- Use Python `shutil.copy2` for file copies
- Use `pathlib` for all paths
- Always dry-run first on baseline push
- Never edit project-specific content — only baseline sections
- NEVER overwrite project-specific hooks (only baseline hooks)
- NEVER delete existing hooks not in baseline
- Touch `.ping` after any write to other repos
- Do NOT commit in other repos — dispatch note telling agent to commit
- Log all deployments in controller-note
