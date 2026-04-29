# /launch — Trigger HTML Mirror Workflow (CTRL-006 Git-Projection)

Trigger and verify public HTML mirror deployment for a project.

## Steps

1. If a project name is given, use it. Otherwise ask which project to launch.
2. Run `py -m src.main launch --project $PROJECT --verbose`
3. Wait for workflow completion (default 300s timeout)
4. Verify public mirror files exist on GitHub Pages
5. Report: workflow status, run ID, elapsed time, mirror URL

## Options
- **Trigger + wait:** `py -m src.main launch --project $PROJECT` (default)
- **Trigger only:** `py -m src.main launch --project $PROJECT --no-wait`
- **Verify only:** `py -m src.main launch --project $PROJECT --verify-only`

## Rules
- Ensure `Output/` or `docs/` contains latest built HTML before launch
- Never include secrets, PII, or internal paths in public HTML
- Verify the public mirror after push (check GitHub Pages URL)
- Requires Designer authorization for each new mirror target
