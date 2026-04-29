# /notify — Send GitHub Notification (Issue #66)

Send a notification to GitHub issue #66 (Remote Controller Status Monitor)
using the `notify_github()` utility in `src/utils/utils.py`.

## Usage

Called automatically by hooks after major operations, or manually:

```
py -c "from src.utils.utils import notify_github; notify_github('COMPLETED', 'Manual notification', detail='...')"
```

## Auto-trigger points (via post_action_notify hook)

This notification fires automatically after:
- `/repo-check` completes (repo-sync results)
- `/dev-check` completes (quality review results)
- `/logic-check` completes (plan validation results)
- `/note-verify` completes (ping verification results)
- `/push-baseline` completes (baseline deployment results)
- `/launch` completes (mirror workflow results)
- Remote controller crash/relaunch (via RemoteController.cmd)

## Event types
- `STARTED` — operation began
- `COMPLETED` — operation finished successfully
- `ERROR` — operation failed or needs attention

## Rules
- Always include task name and duration/detail
- Dedup: workflow checks for existing open issue with same title
- Issue #66 is the canonical notification target
- Never include secrets in notification body (GLOBAL-027)
