# nudge_agent.ps1 -- Unified keep-alive + idle nudge agent.
# Combines two functions into one process:
#   1. SetThreadExecutionState loop (prevents Windows sleep at kernel level)
#   2. F15 keystroke on idle (prevents Teams/app idle status)
# No admin rights required.
#
# Usage:
#   powershell.exe -WindowStyle Hidden -File nudge_agent.ps1
#   powershell.exe -WindowStyle Hidden -File nudge_agent.ps1 -ThresholdMinutes 5
#
# Stop:
#   .\stop_nudge.ps1   (or kill by PID saved in nudge_agent_<user>.pid)

param(
    [int]$ThresholdMinutes = 3,
    [int]$CheckIntervalSeconds = 60,
    [string]$LogPath = ""
)

Set-StrictMode -Version Latest

# --- Win32: idle time via GetLastInputInfo ---
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class NudgeHelper {
    // --- Sleep prevention ---
    const uint ES_CONTINUOUS       = 0x80000000u;
    const uint ES_SYSTEM_REQUIRED  = 0x00000001u;

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint SetThreadExecutionState(uint esFlags);

    public static void PreventSleep() {
        SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED);
    }
    public static void RestoreSleep() {
        SetThreadExecutionState(ES_CONTINUOUS);
    }

    // --- Idle detection ---
    // DEV-010: Use TickCount64 to avoid 32-bit overflow after ~24.9 days uptime.
    [DllImport("user32.dll")]
    static extern bool GetLastInputInfo(ref LASTINPUTINFO li);
    [DllImport("kernel32.dll")]
    static extern ulong GetTickCount64();
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }

    public static ulong GetIdleMs() {
        // M-005: Use full 64-bit arithmetic to avoid wrap-around after ~49.7 days.
        // li.dwTime is the low 32 bits of TickCount; reconstruct the full 64-bit
        // value by combining the high bits of TickCount64 with li.dwTime, then
        // correct for potential wrap of the low 32-bit counter.
        var li = new LASTINPUTINFO();
        li.cbSize = (uint)Marshal.SizeOf(li);
        GetLastInputInfo(ref li);
        ulong now64 = GetTickCount64();
        ulong highBits = now64 & 0xFFFFFFFF00000000UL;
        ulong lastInput64 = highBits | (ulong)li.dwTime;
        // If reconstructed lastInput is ahead of now (wrap occurred), step back one cycle.
        if (lastInput64 > now64) lastInput64 -= 0x100000000UL;
        return now64 - lastInput64;
    }
}
"@

if ($ThresholdMinutes -lt 1) { $ThresholdMinutes = 3 }
if ($CheckIntervalSeconds -lt 1) { $CheckIntervalSeconds = 60 }

$nudgeThresholdMs = $ThresholdMinutes * 60 * 1000
$shell = $null

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $PSScriptRoot "nudge_agent.log"
}

# Per-user PID file for multi-admin safety (concurrent admins don't collide).
$userTag = $env:USERNAME
if (-not $userTag) { $userTag = "default" }
$pidFile = Join-Path $PSScriptRoot ("nudge_agent_{0}.pid" -f $userTag)
$legacyPid = Join-Path $PSScriptRoot "nudge_agent.pid"

# --- Single-instance guard (PID-file based) ---
if (Test-Path $pidFile) {
    $existingPidRaw = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($existingPidRaw -match '^\d+$') {
        $existingPidInt = [int]$existingPidRaw
        if ($existingPidInt -ne $PID) {
            $existingProc = Get-Process -Id $existingPidInt -ErrorAction SilentlyContinue
            if ($existingProc) {
                Write-Host "Nudge agent already running (PID $existingPidInt) -- exiting duplicate."
                exit 0
            }
        }
    }
}

function Write-Log {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message" -Encoding utf8
}

# Save PID -- per-user file + legacy unsuffixed for backwards compat
$PID | Out-File -FilePath $pidFile -Encoding ascii -Force
$PID | Out-File -FilePath $legacyPid -Encoding ascii -Force

# Remove stale keep_alive PID file (merged into this script)
$keepAlivePid = Join-Path $PSScriptRoot "keep_alive_agent.pid"
if (Test-Path $keepAlivePid) { Remove-Item $keepAlivePid -Force }

Write-Host "Nudge agent started (PID $PID, threshold ${ThresholdMinutes}m, interval ${CheckIntervalSeconds}s)"
Write-Host "  Sleep prevention: SetThreadExecutionState (kernel) + powercfg (OS level)"
Write-Host "  Idle nudge: F15 keystroke (Teams/app)"
Write-Log "started pid=$PID threshold_min=$ThresholdMinutes interval_sec=$CheckIntervalSeconds"

# Disable sleep/hibernate at OS level (survives process death until stop_nudge restores it).
# ES_SYSTEM_REQUIRED alone is overridden by Windows 11 Modern Standby -- powercfg is the
# reliable floor that keeps the machine on even if this process crashes.
try {
    powercfg /change standby-timeout-ac 0   | Out-Null  # no sleep on AC
    powercfg /change standby-timeout-dc 0   | Out-Null  # no sleep on battery
    powercfg /change hibernate-timeout-ac 0 | Out-Null  # no hibernate on AC
    Write-Log "powercfg: sleep+hibernate disabled (AC+DC)"
} catch {
    Write-Log "powercfg: failed to set timeouts -- $($_.Exception.Message)"
}

try {
    $shell = New-Object -ComObject "Wscript.Shell"
    while ($true) {
        # Keep system awake (kernel level)
        [NudgeHelper]::PreventSleep()

        # Nudge on idle (app level)
        $idleMs = [NudgeHelper]::GetIdleMs()
        $nudgeSent = $false
        if ($idleMs -ge $nudgeThresholdMs) {
            $shell.SendKeys("{F15}")
            $nudgeSent = $true
        }

        Write-Log "heartbeat pid=$PID idle_ms=$idleMs prevent_sleep=1 nudge_sent=$nudgeSent"

        Start-Sleep -Seconds $CheckIntervalSeconds
    }
}
finally {
    # Restore sleep + cleanup
    [NudgeHelper]::RestoreSleep()
    if ($shell) {
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) } catch {}
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
    # Restore OS-level sleep timeouts (Windows defaults: 30min AC, 15min DC)
    try {
        powercfg /change standby-timeout-ac 30  | Out-Null
        powercfg /change standby-timeout-dc 15  | Out-Null
        powercfg /change hibernate-timeout-ac 0 | Out-Null
        Write-Log "powercfg: sleep timeouts restored (AC=30m DC=15m)"
    } catch { }
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
    if (Test-Path $legacyPid) {
        try {
            $legacyContent = (Get-Content $legacyPid -Raw).Trim()
            if ($legacyContent -eq "$PID") { Remove-Item $legacyPid -Force }
        } catch {}
    }
    Write-Log "stopped pid=$PID sleep_restored=1"
    Write-Host "Nudge agent stopped (PID $PID, user $userTag) -- sleep restored"
}
