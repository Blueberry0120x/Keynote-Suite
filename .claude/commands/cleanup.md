# /cleanup — Stale Artifact Scan + Cleanup (GLOBAL-028)

Scan the current repo AND all repos in config/local_repos.json for stale artifacts.

## Steps

1. For NP_ClaudeAgent (writable):
   - Delete all `__pycache__/` dirs (outside .venv/.git)
   - Delete `.pytest_cache/`
   - Delete `*.bak`, `*.old`, `*.orig`, `*.tmp`, `*~`, `*.copy`, `*.rej` in active paths
   - Delete stale `.pid` files where the process is dead
   - Delete stale `.log` files in tools/

2. For all other repos (read-only — dispatch only):
   - Scan for stale artifacts using Python pathlib (NEVER find.exe)
   - Report findings per repo
   - If any found: write CLEANUP DISPATCH to that repo's controller-note/ + touch .ping

3. Report summary table to user

Use `pathlib.Path.rglob()` for scanning. NEVER use `find.exe` (Defender T1552.004).
