# /open-folder — Launch VS Code New Window for a Repo

Open a project folder in a **new** VS Code window instance.

## Why this exists

On Windows, the `code` command in Git Bash resolves to a Node.js wrapper
(`ELECTRON_RUN_AS_NODE=1`) that silently ignores `--new-window`. You must
launch `Code.exe` directly via PowerShell `Start-Process` to get a true
new window.

## Usage

```
/open-folder <folder-path-or-repo-name>
```

## Steps

1. **Resolve the folder path:**
   - If a full path is given (e.g. `D:\DevOps\Dynamo-Engine`), use it directly.
   - If a repo short name is given (e.g. `Dynamo-Engine`), look it up in
     `config/local_repos.json` to resolve the full local path.
   - Verify the folder exists before proceeding.

2. **Launch VS Code in a new window:**
   ```bash
   powershell.exe -NoProfile -Command "\$code = Join-Path \$env:LOCALAPPDATA 'Programs\Microsoft VS Code\Code.exe'; if (-not (Test-Path \$code)) { \$code = 'C:\Program Files\Microsoft VS Code\Code.exe' }; \$env:ELECTRON_RUN_AS_NODE=''; Start-Process \$code -ArgumentList '--new-window','<FOLDER_PATH>' -PassThru | Select-Object Id"
   ```
   - **CRITICAL:** Must clear `ELECTRON_RUN_AS_NODE` first — Git Bash inherits
     this env var which makes Code.exe run as Node.js instead of Electron.
   - **NEVER hardcode** the VS Code path — use `$env:LOCALAPPDATA` to resolve it
     dynamically so the command works across machines and user accounts.

3. **Verify the window opened** (wait ~6 seconds for VS Code to initialize):
   ```bash
   powershell.exe -NoProfile -Command "Get-Process Code | Where-Object { \$_.MainWindowTitle -ne '' } | Select-Object Id, MainWindowTitle | Format-Table -AutoSize"
   ```
   - Confirm a window title containing the folder name appears in the list.
   - If not found after 10 seconds, report failure.

## Key details

- **Never use** `code`, `code.cmd`, or `code -n` from Git Bash — they route
  through the Node.js shim and silently fail to open new windows.
- **Never hardcode** the VS Code path (e.g. `C:\Users\<name>\...`) — use
  `$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe` with a fallback to
  `C:\Program Files\Microsoft VS Code\Code.exe` for system-wide installs.
- **Always use** `Start-Process ... Code.exe` via PowerShell for reliable new-window launch.
- **Always clear** `$env:ELECTRON_RUN_AS_NODE=''` before `Start-Process` — Git Bash
  leaks this env var which causes Code.exe to run as Node.js, silently failing.
- The `--new-window` flag on Code.exe (not the Node shim) forces a separate instance.
