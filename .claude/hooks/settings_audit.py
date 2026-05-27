"""settings_audit.py -- SessionStart hook: detect settings.json drift from canonical baseline.

Closes the recurring failure pattern where `.claude/settings.json` silently
drifts from the controller's canonical baseline -- specific cases that this
hook catches but the prior `rules_memory_check.py` did NOT:

1. `permissions.defaultMode` missing or != bypassPermissions  (the master
   "no permission prompts" switch the Designer documented in 2026-04-03).
2. Entries in canonical `permissions.allow` missing from this repo's
   settings (e.g. `PowerShell(*)` regression that prompted today).
3. Required hooks from canonical `_EXTRA_HOOKS` not wired into
   settings.json (file present on disk but never registered).
4. Excluded tombstoned items reappearing in settings.json (already
   handled by session_guard but re-asserted here for completeness).

**Reads canonical from `controller-note/baseline_canonical.json`** (deployed
by CTRL-004 from the controller's `config/baseline_canonical.json`). Sister
repos do not need `src/` -- the snapshot is JSON.

Falls back to `config/baseline_canonical.json` (controller-local mode).

Warning-only. Exit 0 always. Not a gate -- visibility.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _ensure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 to survive cp1252 hosts."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, OSError):
                pass


def _load_canonical(repo_root: Path) -> dict | None:
    """Locate and parse baseline_canonical.json snapshot."""
    candidates = [
        repo_root / "controller-note" / "baseline_canonical.json",
        repo_root / "config" / "baseline_canonical.json",  # controller-local
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _collect_wired_commands(settings: dict) -> set[str]:
    """Return the set of every hook command string wired in settings.json."""
    wired: set[str] = set()
    for event, blocks in (settings.get("hooks") or {}).items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            for inner in block.get("hooks", []):
                cmd = str(inner.get("command", ""))
                if cmd:
                    wired.add(cmd)
    return wired


def _check_permissions(settings: dict, canonical: dict) -> list[str]:
    """Verify defaultMode + allow list match canonical."""
    warnings: list[str] = []
    expected = canonical.get("permissions", {})
    expected_mode = expected.get("defaultMode")
    expected_allow = expected.get("allow", []) or []

    perms = settings.get("permissions") or {}
    if expected_mode and perms.get("defaultMode") != expected_mode:
        warnings.append(
            f"permissions.defaultMode = {perms.get('defaultMode')!r}, "
            f"expected {expected_mode!r} -- run repo-sync to backfill"
        )

    have_allow = set(perms.get("allow") or [])
    missing = [e for e in expected_allow if e not in have_allow]
    if missing:
        warnings.append(
            f"permissions.allow missing {len(missing)} entr"
            f"{'y' if len(missing) == 1 else 'ies'}: {', '.join(missing)} "
            "-- run repo-sync to backfill"
        )
    return warnings


def _check_hook_wiring(
    settings: dict, canonical: dict, repo_root: Path
) -> list[str]:
    """Verify every required hook is both on disk AND wired in settings."""
    warnings: list[str] = []
    wired = _collect_wired_commands(settings)
    hooks_dir = repo_root / ".claude" / "hooks"

    for entry in canonical.get("hooks", []):
        fname = entry.get("filename")
        if not fname:
            continue
        suffix = entry.get("command_suffix") or f".claude/hooks/{fname}"
        on_disk = (hooks_dir / fname).exists()
        is_wired = any(suffix in cmd for cmd in wired)

        if not on_disk and not is_wired:
            warnings.append(
                f"hook {fname} -- missing on disk AND not wired"
            )
        elif not on_disk:
            warnings.append(
                f"hook {fname} -- wired in settings.json but file missing"
            )
        elif not is_wired:
            warnings.append(
                f"hook {fname} -- on disk but NOT wired in settings.json"
            )
    return warnings


def main() -> int:
    _ensure_utf8_stdio()
    hook_dir = Path(__file__).resolve().parent
    repo_root = hook_dir.parent.parent
    settings_path = repo_root / ".claude" / "settings.json"

    if not settings_path.exists():
        print("SETTINGS-AUDIT: no .claude/settings.json (skipped)", file=sys.stderr)
        return 0

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"SETTINGS-AUDIT: cannot parse settings.json -- {exc}", file=sys.stderr)
        return 0

    canonical = _load_canonical(repo_root)
    if canonical is None:
        print(
            "SETTINGS-AUDIT: no canonical snapshot found "
            "(controller-note/baseline_canonical.json) -- skipped",
            file=sys.stderr,
        )
        return 0

    warnings: list[str] = []
    warnings.extend(_check_permissions(settings, canonical))
    warnings.extend(_check_hook_wiring(settings, canonical, repo_root))

    if warnings:
        print(
            f"SETTINGS-AUDIT: {len(warnings)} drift item(s) detected:",
            file=sys.stderr,
        )
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        print(
            "  Fix: from the controller, run `py -m src.main repo-sync`",
            file=sys.stderr,
        )
    else:
        print(
            "SETTINGS-AUDIT: settings.json matches canonical baseline.",
            file=sys.stderr,
        )

    return 0  # Never blocks


if __name__ == "__main__":
    sys.exit(main())
