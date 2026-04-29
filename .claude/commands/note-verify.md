# /note-verify — Round-Trip Ping Verification (CTRL-009)

Run the Note-Verify round-trip orchestra across all repos.

## Steps

1. Run `py -m src.main note-verify --dry-run` first to preview current ping state
2. Show the user the state table (which repos have unread pings, which are clear)
3. If user approves, run the full round-trip:
   `py -m src.main note-verify --subject "Sync check" --body "Round-trip verify"`
4. Report results: which repos acknowledged, which are pending, which failed

## Round-trip flow
1. Push upnote + touch `.ping` in all repos
2. Wait for agents to acknowledge
3. Check which repos responded (ping mtime comparison)
4. If all clear: commit all repos + send notification
5. If partial: log pending repos, retry once
6. If still pending: flag for Designer review

## Rules
- Always dry-run first to show state
- Never skip the verification step
- Commit controller-note/ in ALL repos regardless of acknowledgment
