#!/usr/bin/env bash
# ============================================================
#  RemoteController.sh -- Linux watchdog for Claude Remote Control
#  (cross-platform counterpart of RemoteController.cmd; XPLAT-001)
#
#  WATCHDOG: If claude remote-control exits for ANY reason, this
#  script waits 5 seconds and relaunches. Only SIGTERM on this
#  script, a reboot, or the stop() flow breaks the loop.
#
#  SINGLE INSTANCE (per user): starting this script replaces any
#  previous watchdog for the SAME user. Other users' sessions on
#  the same host are untouched (multi-admin safe).
#
#  ALWAYS-ON: for login-less operation run as the supervising
#  service via the systemd template at
#    tools/systemd/np-claude-remote-control@.service
#
#  This is the Linux half of the CTRL-008 stack and is also the
#  execution substrate Ether (see memories/entity_ether.md) will
#  eventually run under. Keep it dependency-light.
# ============================================================

set -u

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

USER_TAG="${USER:-$(id -un 2>/dev/null || echo default)}"
# Session name derives from the repo folder so this portable launcher can
# run in any repo without PID-lock collision. Overridable via 1st arg.
REPO_NAME="$(basename "$REPO_ROOT")"
SESSION_NAME="${1:-${REPO_NAME}_Controller_${USER_TAG}}"

LOG="$REPO_ROOT/tools/remote_controller.log"
WATCHDOG_LOCK="$REPO_ROOT/tools/remote_controller_watchdog_${USER_TAG}.pid"
NUDGE_PY="$REPO_ROOT/tools/linux_nudge_agent.py"
NUDGE_PID_FILE="$REPO_ROOT/tools/nudge_agent_${USER_TAG}.pid"

# Claude CLI discovery (XPLAT-001: match remote_invoke.py Linux branch).
find_claude() {
    for candidate in \
        "$HOME/.local/bin/claude" \
        "/usr/local/bin/claude" \
        "/opt/claude-code/bin/claude" \
        "$(command -v claude 2>/dev/null || true)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

CLAUDE="$(find_claude || true)"
if [ -z "$CLAUDE" ]; then
    echo "[$(date -Is)] [user=$USER_TAG] FATAL: claude CLI not found on PATH or known locations." >> "$LOG"
    exit 127
fi

log() {
    printf '[%s] [user=%s] [session=%s] %s\n' \
        "$(date -Is)" "$USER_TAG" "$SESSION_NAME" "$*" >> "$LOG"
}

# --- SINGLE INSTANCE GUARD (per user) -----------------------
if [ -f "$WATCHDOG_LOCK" ]; then
    OLD_PID="$(cat "$WATCHDOG_LOCK" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill -TERM "$OLD_PID" 2>/dev/null || true
        log "Killed previous watchdog (PID $OLD_PID)."
        sleep 1
    fi
fi
echo "$$" > "$WATCHDOG_LOCK"

# --- KILL PRIOR SESSIONS (exact session-name match, this user only) ---
# ps matches only processes owned by $USER_TAG; name uses the exact
# SESSION_NAME so user-A and user-B sessions don't overlap.
pkill_session() {
    # shellcheck disable=SC2009
    pids=$(ps -u "$USER_TAG" -o pid=,args= 2>/dev/null \
        | awk -v n="$SESSION_NAME" '$0 ~ ("--name[ =]"n"($|[^A-Za-z0-9_-])") {print $1}')
    for pid in $pids; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
    for pid in $pids; do
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
    done
}
pkill_session

# --- NUDGE / KEEP-AWAKE AGENT -------------------------------
# Linux equivalent of nudge_agent.ps1: a lightweight Python
# heartbeat subprocess. Inhibits idle-suspend via systemd-inhibit
# when available, otherwise just runs a periodic touch so external
# monitors see liveness. Never tied to parent lifetime (uses nohup).
start_nudge() {
    if [ ! -f "$NUDGE_PY" ]; then
        log "WARNING: Nudge script $NUDGE_PY missing -- skipping keep-alive."
        return 0
    fi
    # Stop any stale per-user nudge first.
    if [ -f "$NUDGE_PID_FILE" ]; then
        old_np="$(cat "$NUDGE_PID_FILE" 2>/dev/null || true)"
        if [ -n "$old_np" ] && kill -0 "$old_np" 2>/dev/null; then
            kill -TERM "$old_np" 2>/dev/null || true
        fi
        rm -f "$NUDGE_PID_FILE"
    fi
    # Launch detached. systemd-inhibit is used if present to hold
    # an idle/sleep lock for the duration of the nudge process.
    if command -v systemd-inhibit >/dev/null 2>&1; then
        nohup systemd-inhibit \
            --what=idle:sleep \
            --who="np-claude-remote-control" \
            --why="Claude remote-control watchdog active" \
            python3 "$NUDGE_PY" --pid-file "$NUDGE_PID_FILE" \
            >>"$LOG" 2>&1 &
    else
        nohup python3 "$NUDGE_PY" --pid-file "$NUDGE_PID_FILE" \
            >>"$LOG" 2>&1 &
    fi
    sleep 1
    if [ -f "$NUDGE_PID_FILE" ]; then
        log "Nudge agent started (PID $(cat "$NUDGE_PID_FILE"))."
    else
        log "WARNING: Nudge agent did not write PID file."
    fi
}

ensure_nudge_alive() {
    if [ -f "$NUDGE_PID_FILE" ]; then
        np="$(cat "$NUDGE_PID_FILE" 2>/dev/null || true)"
        if [ -n "$np" ] && kill -0 "$np" 2>/dev/null; then
            return 0
        fi
        log "Nudge agent (PID ${np:-?}) died -- restarting..."
    fi
    start_nudge
}

start_nudge

# --- NOTIFY: INITIAL LAUNCH --------------------------------
log "Starting Remote Controller (initial launch) -- CLI: $CLAUDE"

# --- WATCHDOG LOOP -----------------------------------------
cleanup() {
    log "Watchdog received termination signal -- exiting."
    rm -f "$WATCHDOG_LOCK"
    exit 0
}
trap cleanup INT TERM

while true; do
    ensure_nudge_alive

    "$CLAUDE" remote-control --name "$SESSION_NAME"
    EXIT_CODE=$?
    log "Remote Controller exited (code: $EXIT_CODE). Restarting in 5s..."
    sleep 5
    log "Remote Controller RELAUNCHED (recovery from exit $EXIT_CODE)"
done
