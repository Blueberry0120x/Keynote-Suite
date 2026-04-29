# /launch-nudge — Start/Stop Unified Keep-Alive + Nudge Agent

Keyword: **"launch nudge"**

Manages the unified `nudge_agent.ps1` — one process that combines:
- **Keep-alive:** `SetThreadExecutionState` loop (prevents Windows sleep at kernel level)
- **F15 nudge:** keystroke on idle > 3 min (prevents Teams/app idle status)

## Steps

### Start
1. Check if already running: read `tools/nudge_agent.pid`, verify PID is alive
2. If running: report PID + uptime, skip start
3. If not running: launch via `wscript.exe NudgeAgent.vbs` (truly hidden — SW_HIDE at Win32 level)
   - `Start-Process wscript.exe -ArgumentList '"<repo_root>\NudgeAgent.vbs"' -WindowStyle Hidden`
   - **Never** use `powershell -WindowStyle Hidden` directly — it does NOT suppress the console reliably on PS 5.1
4. Wait 3s then confirm PID saved to `tools/nudge_agent.pid`

### Stop
1. Read `tools/nudge_agent.pid`
2. Kill process: `Stop-Process -Id <PID> -Force`
3. Confirm stopped; delete PID file

### Status
1. Read `tools/nudge_agent.pid`
2. Cross-check with `tasklist` for powershell.exe
3. Report: running/stopped, PID, uptime estimate

## Rules
- Only ONE nudge agent at a time (kill before re-launch)
- Windows only — Linux uses the Python heartbeat via `remote-invoke` (XPLAT-001)
- Never dump full CommandLine from tasklist (GLOBAL-027, PID + name only)
- This replaces both `keep_alive_agent.ps1` (legacy) and any separate F15 scripts
- Legacy `keep_alive_agent.pid` is auto-deleted by `nudge_agent.ps1` on startup
