# /adu-scraper — ADU Pre-Approved Plan Downloader (CTRL-REF)

Downloads PDF and CAD files for California pre-approved ADU plans into
`reference/pre_app-adu/{jurisdiction}/pdf/` and `reference/pre_app-adu/{jurisdiction}/cad/`.

## Folder Structure (enforced)

```
reference/pre_app-adu/
  {Jurisdiction}/
    pdf/    ← all .pdf files
    cad/    ← all .dwg / .dxf / .rvt files
  download_log.jsonl   ← all attempts logged here (auto, via tool)
  README.md            ← jurisdiction index
```

File naming: `{description}-{suffix}.{ext}`
- `-cty` = city jurisdiction
- `-cou` = county jurisdiction

## CLI Usage

```bash
# Download files for a jurisdiction
py tools/adu_scraper.py download \
  --jurisdiction San_Diego --suffix cou \
  --referer "https://www.sandiegocounty.gov/content/sdc/pds/bldg/adu_plans.html" \
  "https://example.gov/plan_a.pdf=PlanA_1200sf" \
  "https://example.gov/plan_a.dwg=PlanA_1200sf"

# List all downloaded files + log summary
py tools/adu_scraper.py list

# Retry all failed downloads
py tools/adu_scraper.py retry-failed
```

## Steps (when user says "scrape ADU plans" or "add jurisdiction X")

1. Research the jurisdiction's ADU plan page — look for PDF AND CAD FILE links
   - **Never trust the bot-blocked page** — always inspect in browser or use curl with Referer
   - CAD links are often hidden (not in search results) — hover over buttons to see URL
2. Run `py tools/adu_scraper.py download --jurisdiction X --suffix cty|cou [urls]`
3. Tool logs every attempt to `download_log.jsonl` automatically
4. Move files to correct subfolder: `pdf/` or `cad/`
5. Update `README.md` index
6. Commit — `threshold_commit.py` + `cross_repo_ping.py` hooks fire automatically

## Logging

All downloads logged to `reference/pre_app-adu/download_log.jsonl`:
```json
{"ts": "2026-04-03T...", "status": "OK", "jurisdiction": "San_Diego",
 "file": "PDS670_1200sf-cou.dwg", "type": "DWG", "size_bytes": 234000, "url": "..."}
```
- `status`: `OK` | `FAIL`
- `type`: `PDF` | `DWG` | `HTML_ERROR` (CDN block) | `UNKNOWN`
- Failed downloads are auto-deleted (no corrupt stubs left on disk)

## CAD Discovery Pattern

Many jurisdictions have DWG files not shown in search results.
**Always check by hovering over "CAD FILE" buttons in the browser.**
Known URL patterns that worked:
- San Diego County: `pds670_acad.dwg` (suffix `_acad` on the PDF stem)
- Del Mar: `DocumentCenter/View/{id}/PLAN-NAME-CAD` (no extension in URL)

## Hook Coverage

| Event | Hook | What it does |
|---|---|---|
| PostToolUse/Bash (git commit) | `cross_repo_ping.py` | Pings controller upnote |
| PostToolUse/Edit\|Write | `threshold_commit.py` | Auto-commits if >2 files or >200 lines |
| PostToolUse/Edit\|Write | `auto_ping.py` | Pings if cross-repo write |
| PostToolUse/Bash | `secret_scanner.py` | Scans output for tokens/keys |
| Download logging | **adu_scraper.py itself** | Writes to download_log.jsonl on every attempt |
