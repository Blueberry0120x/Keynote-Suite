# /logic-check — Strategic Planning Validation (CTRL-010)

Validate a proposed plan before execution using multi-persona deliberation.

## Usage

The user provides a plan description. Pass it to the logic-check engine:

```
py -m src.main logic-check --target "$PLAN_DESCRIPTION" --verbose
```

## Steps

1. Ask user for the plan/decision to validate (if not already provided)
2. Run `py -m src.main logic-check --target "..." --max-rounds 50 --clean-goal 10`
3. Report the deliberation result: validated or concerns found
4. If concerns found: list them with impact level and category
5. Save report to `report/`

## How it differs from /dev-check
- **/dev-check** reviews COMPLETED work for quality (looks backward)
- **/logic-check** validates PROPOSED plans for soundness (looks forward)
- Same multi-persona engine, different purpose and persona pool

## Rules
- 10 consecutive clean rounds = plan validated
- Never auto-approve — show user the full deliberation log
- If concerns have HIGH impact: recommend plan revision before proceeding
