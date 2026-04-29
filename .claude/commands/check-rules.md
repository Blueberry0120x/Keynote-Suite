# /check-rules — Verify Rules, Memory, and Hooks are Consistent

Quick health check that everything is wired and nothing is stale.

## Steps

1. **Rules check:**
   - Verify `CLAUDE.md` exists and contains XPLAT-001
   - Verify `report/global_rules.md` exists and points to latest snapshot
   - Verify `.claude/CLAUDE.md` exists and matches root version
   - Compare hook count in `settings.json` vs `config/hook_registry.json`

2. **Memory check:**
   - List all active memory entries
   - Flag any that reference resolved issues, old paths, or retired repos
   - Flag any that contradict current CLAUDE.md rules

3. **Hook check:**
   - Verify all hooks in `settings.json` have matching `.py` files
   - Verify all hooks in `hook_registry.json` are wired in settings
   - Report any orphaned hooks (file exists but not in settings)

4. **Skill check:**
   - Verify all `.claude/commands/*.md` files are valid
   - Cross-reference with `hook_registry.json` skills section

5. **Report:** table of what passed, what's stale, what's missing

## Rules
- This is a read-only check — it does NOT fix anything
- Use `/push-baseline` to actually deploy fixes
- Run this at start of any major session
