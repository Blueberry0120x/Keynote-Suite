# /done — Completion Gate (MANDATORY)

CRITICAL: You MUST run this before declaring ANY task complete.

1. Clean all `__pycache__/` and `.pytest_cache/` dirs (outside .venv/.git)
2. Run `py tools/completion_gate.py`
3. If it prints **COMPLETION GATE PASSED** — you may declare done
4. If it prints **BLOCKED** — fix ALL failures, then re-run. Loop until PASSED.
5. NEVER say "done", "complete", "all clean", or "100%" without seeing PASSED.

This is not optional. Violation = stop and admit error.
