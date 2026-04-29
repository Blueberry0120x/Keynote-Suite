# check-pings

Run `py tools/check_pings.py` to scan all repos for unread pings.

If any UNREAD PINGs are reported:
1. Announce each one: "New ping from {repo} — reading now"
2. Read the upnote file from that repo's `controller-note/` folder (check both `controller-upnote.md` and `{repo}-upnote.md`)
3. Touch `.last-read` in that repo's `controller-note/` to acknowledge
4. Summarize findings to the user

This is a BLOCKING operation — do not proceed with other work until all pings are acknowledged.
