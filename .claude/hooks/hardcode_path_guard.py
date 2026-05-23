"""hardcode_path_guard.py -- PreToolUse hook: blocks writes with hardcoded machine paths.

Fires on Write/Edit tool calls targeting Python, PowerShell, Bash, CMD, and
JSON files (except known machine-local gitignored configs). Scans the content
about to be written for hardcoded absolute paths that will break on any other
machine.

Exit codes:
  0 = ALLOW (no violations)
  2 = BLOCK (hardcoded path found) -- includes fix guidance in stderr

Enforces: GLOBAL-004 (Script Root Derivation), XPLAT-001

Patterns blocked:
  - Windows drive-letter paths: C:\\, D:\\, E:\\... in source files
  - Unix home paths: /home/username/, /Users/username/
  - Specific usernames in paths: /c/Users/napham, /home/natha

Exemptions (not blocked):
  - config/local_repos.json  (gitignored machine-local file)
  - config/terminal/settings.json  (already uses %USERPROFILE%)
  - tests/  (test fixtures with mock paths are acceptable)
  - *.md documentation files
  - .git/ internals
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# Patterns that indicate a hardcoded machine-specific path
_HARDCODED_PATH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Windows absolute drive paths in string literals (Python/PS1/JSON)
    (re.compile(r"""["'`][A-Za-z]:\\\\"""), "Windows drive path in string literal (use env var or shutil.which)"),
    (re.compile(r"""["'`][A-Za-z]:/"""), "Windows drive path (forward slash) in string literal"),
    # Unix absolute paths with specific usernames (not generic /usr/... or /etc/...)
    (re.compile(r"""/c/Users/\w+/"""), "Git-Bash absolute user path (use $HOME instead)"),
    (re.compile(r"""/home/[a-z][a-z0-9_]{2,}/"""), "Unix hardcoded home path (use $HOME instead)"),
    (re.compile(r"""/Users/[A-Za-z][A-Za-z0-9_]{2,}/"""), "macOS hardcoded home path (use $HOME instead)"),
]

# Files that are explicitly allowed to contain absolute paths
_EXEMPT_SUFFIXES = {".md", ".txt", ".rst", ".json.bak"}
_EXEMPT_NAMES = {
    "local_repos.json",   # gitignored machine-local path map
}
_EXEMPT_PREFIXES = (
    "tests/",
    "tests\\",
    ".git/",
    ".git\\",
)

# File extensions that should be checked
_CHECKED_EXTENSIONS = {".py", ".ps1", ".psm1", ".psd1", ".cmd", ".bat", ".sh", ".json"}


def _should_check(file_path: str) -> bool:
    """Return True if the file path should be checked for hardcoded paths."""
    p = Path(file_path)
    suffix = p.suffix.lower()
    name = p.name

    # Only check source files
    if suffix not in _CHECKED_EXTENSIONS:
        return False

    # Exempt specific files and directories
    if name in _EXEMPT_NAMES:
        return False
    if suffix in _EXEMPT_SUFFIXES:
        return False

    normalized = file_path.replace("\\", "/")
    for prefix in _EXEMPT_PREFIXES:
        normalized_prefix = prefix.replace("\\", "/")
        if normalized_prefix in normalized:
            return False

    return True


def _scan_content(content: str) -> list[str]:
    """Return list of violation messages found in content."""
    violations: list[str] = []
    for pattern, message in _HARDCODED_PATH_PATTERNS:
        if pattern.search(content):
            violations.append(message)
    return violations


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0  # Can't parse input — allow

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only intercept Write and Edit operations
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0

    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if not file_path or not _should_check(file_path):
        return 0

    # For Write: check "content"; for Edit: check "new_string"
    content_to_check = ""
    if tool_name == "Write":
        content_to_check = tool_input.get("content", "")
    elif tool_name in ("Edit", "MultiEdit"):
        content_to_check = tool_input.get("new_string", "")
        # MultiEdit has a list of edits
        if not content_to_check and tool_name == "MultiEdit":
            edits = tool_input.get("edits", [])
            content_to_check = "\n".join(e.get("new_string", "") for e in edits)

    if not content_to_check:
        return 0

    violations = _scan_content(content_to_check)
    if not violations:
        return 0

    # Build actionable guidance
    guide_lines = [
        "WRITE BLOCKED — hardcoded machine path detected in file to be written.",
        f"File: {file_path}",
        "",
        "Violations found:",
    ]
    for v in violations:
        guide_lines.append(f"  - {v}")
    guide_lines += [
        "",
        "Fix by using environment/system variables instead:",
        "  Python:      shutil.which('tool') or Path(os.environ.get('ProgramFiles')) / 'Tool'",
        "  PowerShell:  $PSScriptRoot, $env:ProgramFiles, $env:USERPROFILE",
        "  CMD batch:   %~dp0, %ProgramFiles%, %USERPROFILE%, %SystemRoot%",
        "  Bash/sh:     $HOME, $(dirname \"$0\"), command -v tool",
        "  JSON config: use %USERPROFILE% (tracked files) or absolute in gitignored local_repos.json",
        "",
        "See: memories/repo/new_machine_migration.md — Dynamic Path Conventions table",
    ]
    print("\n".join(guide_lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
