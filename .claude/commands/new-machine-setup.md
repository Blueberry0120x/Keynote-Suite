# new-machine-setup

Bootstrap NP_ClaudeAgent on a new computer (or after a fresh clone).

## What this does

Runs the full new-machine bootstrap sequence to ensure the environment is
correctly configured — local path mapping, venv, nudge agent, remote
controller, and compliance check.

## Steps (executed in order)

1. **Verify workspace path** — confirm `(Get-Location)` matches expected layout
2. **Create `config/local_repos.json`** — machine-local path map (gitignored);
   always use absolute path, NOT `%USERPROFILE%` (two-account Windows systems).
3. **Install venv & dependencies** — `python -m venv .venv && pip install -e ".[dev]"`
4. **Run test suite** — `python -m pytest tests/ -v`
5. **Run compliance check** — `python -m src.main analyze --project NP_ClaudeAgent`
6. **Launch NudgeAgent** — `.\NudgeAgent.cmd` → verify 1 process in PID file
7. **Launch RemoteController** — `.\RemoteController.vbs`
8. **Check pings** — `python -m src.main controller-note --scan`

## Quick reference

```powershell
# Get exact path (copy this into local_repos.json)
(Get-Location).Path

# Create local_repos.json
$path = (Get-Location).Path
'{ "repos": { "NP_ClaudeAgent": "' + $path.Replace('\', '\\') + '" } }' |
    Set-Content config\local_repos.json -Encoding utf8

# Verify analyze
python -m src.main analyze --project NP_ClaudeAgent

# Verify nudge single-instance
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'powershell' -and $_.CommandLine -like '*nudge_agent*' } |
  Select-Object ProcessId
```

## Common pitfalls

- `%USERPROFILE%` may point to a different Windows account than your workspace
  user folder. Use `(Get-Location).Path` instead.
- If NudgeAgent spawns duplicates after multiple launches, run `.\tools\stop_nudge.ps1`
  then `.\NudgeAgent.cmd` — the PID-file single-instance guard will prevent duplication.
- The `config/local_repos.json` file is gitignored intentionally. You MUST create
  it manually on every new machine.

## See also

- `memories/repo/new_machine_migration.md` — full root-cause table + conventions
- `.github/Essential_DevSetup.cmd` — OS-level tool bootstrap (winget, Tesseract, 7-Zip)
- `tools/nudge_agent.ps1`, `tools/stop_nudge.ps1`
