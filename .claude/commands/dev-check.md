# /dev-check — Multi-Persona Quality Review (CTRL-007)

Run the Dev-Check quality gate on current repo or a specified project.

## Steps

1. If a project name is given, use it. Otherwise default to NP_ClaudeAgent.
2. Run `py -m src.main dev-check --project $PROJECT --verbose`
3. Review all findings — CRITICAL and HIGH must be fixed immediately.
4. **Auto-fix loop:** Fix all CRITICAL/HIGH findings, re-run until 10 consecutive clean rounds.
5. Only escalate to user if a finding requires a design decision.
6. Log the dev-check result in `report/`.

## Rules
- Minimum 10 consecutive clean rounds to pass
- Covers: architecture, security, UX, performance, accessibility
- Never return broken output to user — fix and re-run
