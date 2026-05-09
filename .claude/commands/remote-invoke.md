# /remote-invoke — CLI Remote Controller (CTRL-008 Session Manager)

> **NOT the same as `/launch`.**
> - `/launch` = CTRL-006: publishes HTML output to a public GitHub Pages mirror. It deploys files.
> - `/remote-invoke` = CTRL-008: starts/checks a background Claude CLI session on this machine. It manages processes.
> These are completely separate. Do not confuse them.

**Keywords (all interchangeable):**
- `invoke remote` / `invoke controller` / `invoke cli`
- `remote cli` / `controller cli` / `start remote` / `start controller`
- `remote session` / `controller session` / `remote status`

Manages CTRL-008 lifecycle: background Claude session + keep-alive nudge.
Multiple sessions are allowed — one per worktree. Each session is named after its repo/worktree.

## Permissions

This skill runs with **free edit permission** — Edit, Write, Bash, and Read are all
pre-approved without prompts. This applies to the current repo directory.

## Steps

1. Detect current repo name and dir:
   ```python
   import subprocess, pathlib
   repo_dir = pathlib.Path.cwd()
   repo_name = subprocess.check_output(
       ["git", "remote", "get-url", "origin"], cwd=repo_dir, text=True
   ).strip().split("/")[-1].replace(".git", "")
   session_name = f"{repo_name}_Controller"
   ```

2. Check current status — run from the **NP_ClaudeAgent controller repo** (has `src.main`):
   ```
   cd C:\Users\NathanPham\DevOps\NP_ClaudeAgent
   py -m src.main remote-invoke --status
   ```
   On Linux: `python -m src.main remote-invoke --status`

   **Fallback (if controller repo unavailable):** check processes directly:
   - Windows: `Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*claude*' } | Select-Object ProcessId, Name`
   - Linux: `ps aux | grep claude`
   - PID file fallback: check `C:\Users\NathanPham\DevOps\NP_ClaudeAgent\tools\{session_name}.pid`

3. Based on status:
   - **No session for this worktree:** Start by running `RemoteController.cmd` from NP_ClaudeAgent, or:
     `cd C:\Users\NathanPham\DevOps\NP_ClaudeAgent && py -m src.main remote-invoke --start --name {session_name}`
   - **Session stale/unresponsive:** Reinvoke: `py -m src.main remote-invoke --reinvoke --name {session_name}`
   - **Session healthy:** Report status, no action needed

4. Verify keep-alive is running (Python heartbeat on Linux / nudge_agent.ps1 on Windows)

5. Report: PID, uptime, keep-alive status, F15 nudge status

## Multiple Sessions (Multi-Worktree)

Multiple sessions running simultaneously is **intentional and expected**.
Each worktree gets its own named session. Do not kill other sessions when starting one.

## Status & Cleanup

1. Run `--status` from NP_ClaudeAgent to list all running sessions
2. Cross-reference PID files in `NP_ClaudeAgent/tools/` with live processes
3. Kill only **orphan** sessions (PID file exists but process dead)
4. Use `--stop --name {name}` to target a specific session

## Keep-Alive Agents

| Agent | Platform | What it does |
|-------|----------|-------------|
| Python heartbeat | Linux | Detached subprocess, SIGTERM on stop |
| `nudge_agent.ps1` | Windows | Sleep prevention + F15 idle keystroke |

## Crash-Loop Diagnostics

When log shows repeated `exited (code: 1) → RELAUNCHED`:

1. Check for first occurrence in log
2. Verify the launch subcommand still exists: `claude --help`
3. Check CLI version: `claude --version`
4. Compare CMD/sh launch line vs available CLI commands — any mismatch = update launcher

**Root cause of 2026-04-02 incident:** `remote-control` subcommand removed in claude v2.1.91.
After any `claude update`, re-run crash-loop diagnostics.

## Rules
- Multiple sessions allowed — one per worktree (NOT a singleton)
- Keep-alive MUST run independently (XPLAT-001: works on Windows + Linux)
- Never dump full command lines — PID + process name only (GLOBAL-027)
- On crash: use `--reinvoke` (stops existing + starts fresh)
- Cross-platform: `ps aux` on Linux, WMIC/CimInstance on Windows, PID-file fallback on both
- `py -m src.main` commands MUST be run from NP_ClaudeAgent — it does not exist in this repo
