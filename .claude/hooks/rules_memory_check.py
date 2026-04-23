"""rules_memory_check.py -- SessionStart hook: deep inventory of hooks + skills.

Runs every session start. session_guard.py owns the blocking gate (file existence).
This hook owns the non-blocking deep inventory:
1. .claude/CLAUDE.md contains XPLAT-001
2. All hooks referenced in settings.json exist as .py files
3. All skills referenced in hook_registry.json exist as .md files

Exit 0 always (warnings only). Not a gate — just visibility.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    # Derive repo root from this hook's location
    # .claude/hooks/rules_memory_check.py -> repo root
    hook_dir = Path(__file__).resolve().parent
    repo_root = hook_dir.parent.parent

    warnings: list[str] = []
    dot_claude_md = repo_root / ".claude" / "CLAUDE.md"

    # 1. XPLAT-001 content check (session_guard owns existence gate)
    if dot_claude_md.exists():
        content = dot_claude_md.read_text(encoding="utf-8")
        if "XPLAT-001" not in content:
            warnings.append(
                "CLAUDE.md missing XPLAT-001 rule — "
                "run /push-baseline to deploy"
            )

    # 2. Verify hooks exist
    settings_file = repo_root / ".claude" / "settings.json"
    if settings_file.exists():
        try:
            settings = json.loads(
                settings_file.read_text(encoding="utf-8"),
            )
            hooks_config = settings.get("hooks", {})
            for event, blocks in hooks_config.items():
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    hook_list = block.get("hooks", [])
                    for hook in hook_list:
                        cmd = hook.get("command", "")
                        # Extract .py path from command
                        for part in cmd.split():
                            part = part.strip('"').strip("'")
                            if part.endswith(".py"):
                                # Resolve $CLAUDE_PROJECT_DIR
                                resolved = part.replace(
                                    "$CLAUDE_PROJECT_DIR",
                                    str(repo_root),
                                )
                                if not Path(resolved).exists():
                                    warnings.append(
                                        f"HOOK MISSING: {part} "
                                        f"(event: {event})"
                                    )
        except (json.JSONDecodeError, OSError):
            warnings.append("settings.json parse error")

    # 3. Verify skills exist
    registry_file = repo_root / "config" / "hook_registry.json"
    if registry_file.exists():
        try:
            registry = json.loads(
                registry_file.read_text(encoding="utf-8"),
            )
            skills = registry.get("skills", {})
            commands_dir = repo_root / ".claude" / "commands"
            for skill_name in skills:
                # /done -> done.md
                md_name = skill_name.lstrip("/") + ".md"
                if not (commands_dir / md_name).exists():
                    warnings.append(
                        f"SKILL MISSING: {skill_name} "
                        f"({commands_dir / md_name})"
                    )
        except (json.JSONDecodeError, OSError):
            warnings.append("hook_registry.json parse error")

    # 4. Report
    if warnings:
        print(
            f"RULES CHECK: {len(warnings)} warning(s):",
            file=sys.stderr,
        )
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    else:
        print(
            "RULES CHECK: all rules, hooks, and skills verified.",
            file=sys.stderr,
        )

    return 0  # Never blocks


if __name__ == "__main__":
    sys.exit(main())
