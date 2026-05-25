## [2026-05-25 15:10] Baseline catch-up: session_guard daily cadence + drift_check wiring -- global_update @claude-cli

**What changed:**
- `tools/session_guard.py` now runs `drift_check status` daily (was weekly)
- `tools/session_guard.py` runs `skill_usage_aggregator` daily (was weekly)
- `tools/session_guard.py` runs `self_improve_retention prune` daily (was weekly)
- New: `tools/drift_check.py` -- surfaces baseline file drift across sister repos
- New: `tools/cross_repo_activity.py` -- Lane E coupling signal (cascade vs session bands)

**Action required:** None. These run automatically at session start. If you see
"Drift check: N drift" at session start, run `py -m src.main repo-sync` from
NP_ClaudeAgent to heal.

*Dispatched by NP_ClaudeAgent Controller -- daily-cadence improvement 2026-05-25*

---
# Controller → Keynote-Suite

> Notes from NP_ClaudeAgent Controller.

---
