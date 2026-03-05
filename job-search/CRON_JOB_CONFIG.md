# Job Search Cron Job Configuration

## Summary

Automated job opportunity scanner running twice daily.

**Schedule:** 8:00 AM MT & 2:00 PM MT (Thursday–Friday, search days)  
**Script:** `job-search/job_search_scanner.py`  
**Output:** 
- Logs new opportunities to `job-search/OPPORTUNITIES.md`
- Sends Telegram alert if new roles found
- Tracks state in `job-search/scanner_state.json`

---

## Setup

### 1. Create Cron Job (8:00 AM MT)

```bash
openclaw cron create \
  --name "job-search-morning" \
  --schedule "0 8 * * 1-5" \
  --command "python3 /Users/pinchy/.openclaw/workspace/job-search/job_search_scanner.py" \
  --timeout 120
```

### 2. Create Cron Job (2:00 PM MT)

```bash
openclaw cron create \
  --name "job-search-afternoon" \
  --schedule "0 14 * * 1-5" \
  --command "python3 /Users/pinchy/.openclaw/workspace/job-search/job_search_scanner.py" \
  --timeout 120
```

### 3. Verify Jobs Created

```bash
openclaw cron list
```

---

## Schedule Details

| Job | Time | Frequency | Days |
|-----|------|-----------|------|
| `job-search-morning` | 8:00 AM MT | Daily | Mon-Fri |
| `job-search-afternoon` | 2:00 PM MT | Daily | Mon-Fri |

---

## What It Does

### Search Execution
1. Searches Indeed, LinkedIn, BuildinColorado for target roles
2. Filters by: Principal/Staff/Manager/Director + $165K+ + Remote/Boulder/Denver
3. Compares against previous runs to detect new opportunities

### Alert Workflow
If **new opportunities found**:
- ✅ Appends to `job-search/OPPORTUNITIES.md` with structured format
- ✅ Sends Telegram message: "🎯 N New Job Opportunities Found"
- ✅ Lists company, title, location, salary, link, date posted
- ✅ Stores state in `scanner_state.json` to avoid duplicates

If **no new opportunities**:
- ✅ Logs "No new opportunities found"
- ✅ Updates lastRun timestamp
- ✅ No Telegram alert (reduces noise)

---

## Implementation Notes

### Current Status (Mar 5, 2026)

**Issue:** Indeed & LinkedIn direct scraping blocked (Cloudflare, ToS violations)

**Solution:** Use OpenClaw web_search tool within cron job to fetch results, then parse

**Next Steps:**
1. Integrate OpenClaw `web_search` API calls instead of direct scraping
2. Test with BuildinColorado (allows scraping)
3. Use LinkedIn search results (not APIs) to extract opportunities
4. Handle Telegram alerts via OpenClaw message tool

### API Integration Options

1. **Indeed API** — Requires paid plan (~$500+/mo)
2. **LinkedIn** — Recruiters API (enterprise only)
3. **BuildinColorado** — Allows web_fetch (free, no API needed)
4. **BraveSearch** — Free with rate limiting (2/min = 2,880/day)

**Recommended Approach:**
- Use `web_search` (Brave API) for Indeed + general search
- Use `web_fetch` for BuildinColorado
- LinkedIn passive search via Indeed results + BuildinColorado

---

## Testing

Run scanner manually to verify:

```bash
python3 /Users/pinchy/.openclaw/workspace/job-search/job_search_scanner.py
```

Expected output:
```
============================================================
Job Search Scanner — 2026-03-05 08:05:00
============================================================

Starting searches...

Total opportunities found: X
After filtering: Y opportunities meet criteria

New opportunities: Z

✅ Opportunities file updated + alert sent
============================================================
```

---

## Troubleshooting

**No opportunities found?**
- Check target criteria (titles, salary, locations)
- Verify search APIs are responding
- Check for Cloudflare blocks on Indeed

**Duplicate opportunities?**
- Check `scanner_state.json` for corrupted state
- Delete scanner_state.json to reset (next run will re-discover)

**Alerts not sending?**
- Verify Telegram provider is online
- Check OpenClaw message tool integration

---

**Last Updated:** March 5, 2026 @ 8:06 AM MT  
**Status:** Ready to deploy cron jobs
