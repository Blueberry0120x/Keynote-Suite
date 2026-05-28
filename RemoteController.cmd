@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  RemoteController.cmd -- Launch Claude Remote Control
REM  for NP_ClaudeAgent Controller
REM
REM  WATCHDOG: If remote-control exits for ANY reason, this
REM  script waits 5 seconds and relaunches. Only a reboot or
REM  explicit kill of THIS script stops the loop.
REM
REM  SINGLE INSTANCE (per user): Starting this script kills any
REM  previous watchdog loop FOR THE SAME USER. Other admins on
REM  the same machine run their own independent watchdog.
REM
REM  MULTI-ADMIN SAFE: session name, PID files, and wmic kill
REM  filter are all namespaced by %USERNAME% so concurrent admin
REM  sessions do not terminate each other's remote-control.
REM
REM  NOTIFICATIONS: Fires GitHub Issue comment on crash + relaunch
REM  so Designer gets notified on phone when away from desk.
REM
REM  Auto-starts on login via Startup shortcut. For login-less
REM  always-on (closed laptop, logged-out desktop) use Task
REM  Scheduler with the template at tools\scheduled_task_remote_controller.xml.
REM ============================================================

REM Session name namespaced by REPO FOLDER + %USERNAME% so this same
REM portable launcher can run in any repo without PID-lock collision.
REM Derive the repo name from this script's own folder (%~dp0).
REM May be overridden via 1st arg.
if "%~1"=="" (
    for %%I in ("%~dp0.") do set "REPO_NAME=%%~nxI"
    set "SESSION_NAME=!REPO_NAME!_Controller_%USERNAME%"
) else (
    set "SESSION_NAME=%~1"
)

REM Detect gh -- search PATH first, then user-local bin, then system install
set "GH="
for /f "usebackq delims=" %%p in (`where gh 2^>nul`) do if not defined GH set "GH=%%p"
if not defined GH if exist "%USERPROFILE%\.local\bin\gh.exe" set "GH=%USERPROFILE%\.local\bin\gh.exe"
if not defined GH if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH=%ProgramFiles%\GitHub CLI\gh.exe"

REM Detect claude CLI -- search PATH first, then user-local bin, then npm global
set "CLAUDE="
for /f "usebackq delims=" %%p in (`where claude 2^>nul`) do if not defined CLAUDE set "CLAUDE=%%p"
if not defined CLAUDE if exist "%USERPROFILE%\.local\bin\claude.exe" set "CLAUDE=%USERPROFILE%\.local\bin\claude.exe"
if not defined CLAUDE set "CLAUDE=%APPDATA%\npm\claude.cmd"

REM Derive repo slug (owner/name) from git remote -- no hardcoded values
set "REPO="
for /f "usebackq delims=" %%r in (`powershell -NoProfile -Command "(git remote get-url origin 2>$null) -replace '^.*github\.com[/:]','' -replace '\.git$',''" 2^>nul`) do set "REPO=%%r"
if not defined REPO set "REPO=Blueberry0120x/NP_ClaudeAgent"
set "LOG=%~dp0tools\remote_controller.log"
set "GUARD=py tools\session_guard.py --no-ping"
set "NUDGE_PS1=%~dp0tools\nudge_agent.ps1"
set "STOP_NUDGE=%~dp0tools\stop_nudge.ps1"
set "WATCHDOG_LOCK=%~dp0tools\remote_controller_watchdog_%USERNAME%.pid"

REM === SINGLE INSTANCE GUARD ===
REM Get this script's own CMD PID via PowerShell parent lookup
set "MY_PID="
for /f "usebackq" %%p in (`powershell -NoProfile -Command "(Get-Process -Id $PID).Parent.Id" 2^>nul`) do set "MY_PID=%%p"

REM Kill previous watchdog instance if a lockfile exists
if exist "%WATCHDOG_LOCK%" (
    set "OLD_PID="
    set /p OLD_PID=<"%WATCHDOG_LOCK%"
    if defined OLD_PID (
        taskkill /F /PID !OLD_PID! >nul 2>&1
        echo [%date% %time%] Killed previous watchdog ^(PID !OLD_PID!^). >> "%LOG%"
    )
)

REM Write own PID to lockfile
if defined MY_PID echo !MY_PID!>"%WATCHDOG_LOCK%"

REM Kill only THIS USER's existing claude remote-control sessions (filter by exact session name).
REM Other admins' sessions (e.g. NP_ClaudeAgent_Controller_otheruser) are untouched.
for /f "tokens=2 delims=," %%p in ('wmic process where "commandline like '%%--name%%!SESSION_NAME!%%'" get processid /format:csv 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul

cd /d "%~dp0"

REM Start nudge agent (sleep prevention + F15 idle nudge)
REM Stop any leftover first, then launch hidden
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STOP_NUDGE%" >nul 2>&1
timeout /t 1 /nobreak >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','\"%NUDGE_PS1%\"' -WindowStyle Hidden" >nul 2>&1
timeout /t 2 /nobreak >nul

REM Verify nudge agent actually started (per-user PID file; matches nudge_agent.ps1 naming).
set "NUDGE_PID_FILE=%~dp0tools\nudge_agent_%USERNAME%.pid"
if exist "!NUDGE_PID_FILE!" (
    set /p NUDGE_PID=<"!NUDGE_PID_FILE!"
    echo [%date% %time%] Nudge agent started ^(PID !NUDGE_PID!^). >> "%LOG%"
) else (
    echo [%date% %time%] WARNING: Nudge agent PID file not found -- may not have started. >> "%LOG%"
)

REM Notify: initial launch (user-tagged so multi-admin activity is distinguishable on Issue #14).
echo [%date% %time%] [user=%USERNAME%] [session=!SESSION_NAME!] Starting Remote Controller ^(initial launch^)... >> "%LOG%"
%GH% issue comment 66 --repo %REPO% --body "[CTRL-008] Remote Controller LAUNCHED at %date% %time% (user=%USERNAME%, session=!SESSION_NAME!). Watchdog active." >nul 2>&1

REM Watchdog loop -- restart on any exit
:loop
%GUARD% >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Session guard blocked remote launch. Retrying in 30s... >> "%LOG%"
    timeout /t 30 /nobreak >nul
    goto loop
)

REM Verify nudge agent is still alive before each CLI launch
if exist "!NUDGE_PID_FILE!" (
    set /p NUDGE_PID=<"!NUDGE_PID_FILE!"
    tasklist /FI "PID eq !NUDGE_PID!" 2>nul | findstr /i "powershell" >nul 2>&1
    if errorlevel 1 (
        echo [%date% %time%] Nudge agent ^(PID !NUDGE_PID!^) died -- restarting... >> "%LOG%"
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STOP_NUDGE%" >nul 2>&1
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','\"%NUDGE_PS1%\"' -WindowStyle Hidden" >nul 2>&1
        timeout /t 2 /nobreak >nul
    )
) else (
    echo [%date% %time%] Nudge agent PID file missing -- restarting... >> "%LOG%"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','\"%NUDGE_PS1%\"' -WindowStyle Hidden" >nul 2>&1
    timeout /t 2 /nobreak >nul
)

"%CLAUDE%" remote-control --name !SESSION_NAME!
set "EXIT_CODE=!ERRORLEVEL!"
echo [%date% %time%] [user=%USERNAME%] [session=!SESSION_NAME!] Remote Controller exited ^(code: !EXIT_CODE!^). Restarting in 5s... >> "%LOG%"

REM Notify: crash + relaunch
%GH% issue comment 66 --repo %REPO% --body "[CTRL-008] Remote Controller CRASHED (exit code: !EXIT_CODE!, user=%USERNAME%, session=!SESSION_NAME!) at %date% %time%. Restarting in 5s..." >nul 2>&1

timeout /t 5 /nobreak >nul

echo [%date% %time%] [user=%USERNAME%] [session=!SESSION_NAME!] Remote Controller RELAUNCHED ^(recovery from exit !EXIT_CODE!^) >> "%LOG%"
%GH% issue comment 66 --repo %REPO% --body "[CTRL-008] Remote Controller RELAUNCHED at %date% %time% (user=%USERNAME%, session=!SESSION_NAME!, recovered from exit !EXIT_CODE!)." >nul 2>&1

goto loop
