"""linux_nudge_agent.py -- Linux counterpart of nudge_agent.ps1.

Purpose: keep the box out of idle-sleep while a Claude remote-control
watchdog is running. On Linux the sleep-prevention work is delegated to
systemd-inhibit (invoked by RemoteController.sh), so this script's only
jobs are:

1. Write a PID file so the watchdog can detect liveness and restart us.
2. Heartbeat: periodically touch a marker file so external monitors
   (CTRL-008, Ether supervisor) can see we're alive.
3. Restore nothing on exit -- systemd-inhibit's lock is released the
   moment its child (this process) terminates, so a clean exit is enough.

XPLAT-001: this is the Linux branch; the Windows branch is
``tools/nudge_agent.ps1``. Keep the surface contracts aligned:
per-user PID file at ``tools/nudge_agent_<user>.pid``.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

HEARTBEAT_INTERVAL_SECONDS = 60


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pid-file",
        required=True,
        type=Path,
        help="path to write this process's PID for watchdog liveness checks",
    )
    parser.add_argument(
        "--heartbeat-file",
        type=Path,
        default=None,
        help="optional path to touch every interval (default: <pid-file>.heartbeat)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=HEARTBEAT_INTERVAL_SECONDS,
        help=f"heartbeat interval in seconds (default: {HEARTBEAT_INTERVAL_SECONDS})",
    )
    return parser.parse_args()


def _install_signal_handlers(pid_file: Path) -> None:
    def _cleanup(signum: int, _frame: object) -> None:
        try:
            if pid_file.exists():
                pid_file.unlink()
        finally:
            sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)


def main() -> int:
    args = _parse_args()
    pid_file: Path = args.pid_file
    heartbeat_file: Path = args.heartbeat_file or pid_file.with_suffix(".heartbeat")
    interval = max(1, args.interval)

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="ascii")

    _install_signal_handlers(pid_file)

    try:
        while True:
            heartbeat_file.touch()
            time.sleep(interval)
    finally:
        if pid_file.exists():
            try:
                pid_file.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
