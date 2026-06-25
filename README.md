# BrokerScan

**Data broker exposure scanner.** Checks 30 data broker sites for your personal information and logs opt-out URLs so you can act fast.

Built for privacy-conscious users who are tired of re-opting out of the same sites every few months.

---

## What it does

- Scans 30 known data brokers (people-search, B2B/recruiter, background check, aggregator)
- Detects whether your name + city appear in listings
- Logs results to a local SQLite database with timestamps
- Surfaces direct opt-out URLs for any site where you're found
- Re-scan scheduler: flags brokers due for re-check after 90 days
- Exports results to CSV

---

## Files

| File             | Purpose                                      |
|------------------|----------------------------------------------|
| `brokerscan.py`  | Core scanner — Playwright-based, CLI         |
| `index.html`     | Dashboard UI — demo mode, works offline      |
| `brokerscan.db`  | Auto-created SQLite database                 |

---

## Setup

```bash
pip install playwright rich sqlite-utils
playwright install chromium
```

---

## Usage

**Basic scan:**
```bash
python brokerscan.py --name "John Doe" --city "Miami" --state "FL"
```

**Full profile scan:**
```bash
python brokerscan.py \
  --name "John Doe" \
  --city "Miami" \
  --state "FL" \
  --email "john@example.com" \
  --phone "3055550000"
```

**High-priority brokers only:**
```bash
python brokerscan.py --name "John Doe" --city "Miami" --state "FL" --priority HIGH
```

**Export to CSV:**
```bash
python brokerscan.py --name "John Doe" --city "Miami" --state "FL" --export results.csv
```

**Only scan sites due for re-check (>90 days since last scan):**
```bash
python brokerscan.py --name "John Doe" --city "Miami" --state "FL" --due-only
```

---

## Status values

| Status    | Meaning                                          |
|-----------|--------------------------------------------------|
| `FOUND`   | Your info detected on this broker site           |
| `CLEAN`   | No listing detected                              |
| `BLOCKED` | Site returned CAPTCHA or rate-limit response     |
| `ERROR`   | Timeout or navigation failure                    |

---

## Broker priority tiers

| Priority | Examples                                         | Why it matters                    |
|----------|--------------------------------------------------|-----------------------------------|
| HIGH     | ZoomInfo, Spokeo, Whitepages, Acxiom, Intelius   | Recruiter-facing, widely scraped  |
| MED      | FastPeopleSearch, Pipl, Epsilon, CoreLogic       | Moderate reach                    |
| LOW      | ClustrMaps, AnyWho, Xlek, Classmates            | Lower traffic but still aggregate |

---

## Limitations

- **CAPTCHAs**: Many high-priority brokers (ZoomInfo, Spokeo) will block automated requests. `BLOCKED` status means you need to check manually.
- **Email verification**: Most opt-out flows require email confirmation — automation gets you to the form, not through it.
- **Re-listing**: Brokers routinely re-add removed data. Re-scan every 90 days. Use `--due-only` to skip already-checked sites.
- **False negatives**: If a broker restructures their HTML, selectors may miss a listing. Treat `CLEAN` as "not detected," not "definitely not listed."

---

## Legal notes (Florida)

Florida's **Digital Bill of Rights (FDBR)** (effective July 2024) gives you:
- The right to request deletion of your personal data
- The right to opt out of data sales
- Enforcement via the Florida AG's office

If a broker ignores a verified deletion request, file a complaint at [myfloridalegal.com](https://www.myfloridalegal.com/).

For unwanted calls/texts, file with the FTC at [reportfraud.ftc.gov](https://reportfraud.ftc.gov/) and register at [donotcall.gov](https://www.donotcall.gov/).

---

## Roadmap

- [ ] Phase 2: Auto-fill opt-out forms for non-CAPTCHA sites
- [ ] Phase 3: Email watcher — detect "your opt-out was processed" confirmations
- [ ] Phase 4: Scheduled re-scan via cron + email digest
- [ ] Web UI: Connect dashboard to live Python backend via Flask/FastAPI

---

## Stack

- Python 3.10+
- [Playwright](https://playwright.dev/python/) — browser automation
- [Rich](https://github.com/Textualize/rich) — terminal output
- SQLite — local scan history
- Vanilla HTML/CSS/JS — dashboard UI
