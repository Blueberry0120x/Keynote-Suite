# stop_nudge.ps1 -- Stop the nudge agent by saved PID
#
# Usage:
#   .\stop_nudge.ps1

Set-StrictMode -Version Latest

# Multi-admin safe: only stop THIS user's nudge agent. Other users' agents
# live under their own nudge_agent_<username>.pid and are untouched.

$userTag = $env:USERNAME
if (-not $userTag) { $userTag = "default" }

$pidFile = Join-Path $PSScriptRoot ("nudge_agent_{0}.pid" -f $userTag)
$legacyPid = Join-Path $PSScriptRoot "nudge_agent.pid"

function Stop-FromPidFile($path) {
    if (-not (Test-Path $path)) { return $false }
    $savedPid = (Get-Content $path -Raw).Trim()
    try {
        Stop-Process -Id $savedPid -Force -ErrorAction Stop
        Write-Host "Nudge agent (PID $savedPid) stopped."
    }
    catch {
        Write-Host "Process $savedPid not found -- may have already exited."
    }
    Remove-Item $path -Force -ErrorAction SilentlyContinue
    return $true
}

$stopped = Stop-FromPidFile $pidFile
if (-not $stopped) { $stopped = Stop-FromPidFile $legacyPid }

if (-not $stopped) {
    # Fallback: find by command line, filtered to processes owned by THIS user.
    $procs = Get-Process powershell*, pwsh* -ErrorAction SilentlyContinue |
        Where-Object {
            try {
                $ci = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
                if (-not $ci) { return $false }
                $owner = $ci | Invoke-CimMethod -MethodName GetOwner -ErrorAction SilentlyContinue
                ($ci.CommandLine -like "*nudge_agent*") -and ($owner.User -eq $userTag)
            } catch { $false }
        }
    if ($procs) {
        $procs | ForEach-Object {
            Stop-Process -Id $_.Id -Force
            Write-Host "Killed nudge agent (PID $($_.Id), user $userTag)"
        }
    }
    else {
        Write-Host "No nudge agent found running for user $userTag."
    }
}
