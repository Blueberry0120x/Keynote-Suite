# /remote-invoke — CTRL-008 Remote Controller (Process + Console)

**Keywords (all interchangeable):**
- `launch remote` / `invoke remote` / `launch controller` / `invoke controller`
- `launch cli` / `invoke cli` / `remote cli` / `controller cli`
- `start remote` / `start controller` / `start cli`

Manages the full CTRL-008 lifecycle: background Claude session + keep-alive nudge.
The console (`py -m src.main controller`) runs **inside** this session — no separate skill needed.

## Steps

1. Check current status: `py -m src.main remote-invoke --status`
2. Based on status:
   - **No session running:** Start with `py -m src.main remote-invoke --start --name NP_ClaudeAgent_Controller`
   - **Session stale/unresponsive:** Reinvoke with `py -m src.main remote-invoke --reinvoke --name NP_ClaudeAgent_Controller`
   - **Session healthy:** Report status, no action needed
3. Verify keep-alive (Python heartbeat on Linux / nudge_agent.ps1 on Windows) is running
4. Report PID, uptime, keep-alive status, F15 nudge status

To open the orchestra console inside the session, run: `py -m src.main controller`

## Status & Cleanup

1. Run `py -m src.main remote-invoke --status` to list sessions
2. Cross-reference PID files in `tools/` with live processes
3. Kill orphan processes (dead PID files, duplicate sessions)
4. If duplicates found: kill all, reinvoke fresh with `--reinvoke`

## Keep-Alive Agents

| Agent | Platform | What it does |
|-------|----------|-------------|
| Python heartbeat | Linux | Detached subprocess, SIGTERM on stop |
| `nudge_agent.ps1` | Windows | Sleep prevention + F15 idle keystroke |

Use `/launch-nudge` to manage the Windows nudge agent independently of the remote session.

## Crash-Loop Diagnostics (run when exit code 1 repeats in log)

When `remote_controller.log` shows repeated `exited (code: 1) → RELAUNCHED` entries:

1. **Check the log for first occurrence:**
   ```
   Get-Content tools\remote_controller.log | Select-String "exited" | Select-Object -First 3
   ```
2. **Verify the launch command still exists in the CLI:**
   ```powershell
   & "$env:USERPROFILE\.local\bin\claude.exe" --help
   ```
   Look for the subcommand being used in `RemoteController.cmd`. If it's missing → CLI was updated and removed it.
3. **Check CLI version:**
   ```powershell
   & "$env:USERPROFILE\.local\bin\claude.exe" --version
   ```
4. **Compare CMD launch line vs available CLI commands.** Any mismatch = update `RemoteController.cmd` + `src/remote_invoke/remote_invoke.py`.
5. **Grep all hardcoded subcommand strings** after any CLI update:
   ```
   grep -rn "remote-control\|remote-invoke\|--name" .claude/hooks/ src/ RemoteController.cmd
   ```

**Root cause of 2026-04-02 incident:** `remote-control` subcommand removed in claude v2.1.91. CMD and `remote_invoke.py` both hardcoded the old subcommand. Watchdog looped for 3+ days unnoticed because log check was not part of `remote-status` skill.

## Rules
- Only ONE remote-control session at a time (enforced by `single_instance` hook)
- Keep-alive MUST run independently (XPLAT-001: works on both Windows and Linux)
- Never dump full command lines (GLOBAL-027 — PID + process name only)
- On crash: use `--reinvoke` (stops existing + starts fresh)
- Cross-platform: `ps aux` on Linux, WMIC on Windows, PID-file fallback on both
- **On any `claude update`:** re-run crash-loop diagnostics above to verify CMD + src still match CLI
