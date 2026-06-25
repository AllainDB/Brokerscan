#!/usr/bin/env python3
"""
BrokerScan — Data Broker Exposure Scanner
Phase 1: Detection + opt-out page logging

Requirements:
    pip install playwright rich sqlite-utils
    playwright install chromium

Usage:
    python brokerscan.py --name "John Doe" --city "Miami" --state "FL" \
                         --email "john@example.com" --phone "3055550000"

    python brokerscan.py --name "John Doe" --city "Miami" --state "FL" \
                         --export results.csv

Database: brokerscan.db (SQLite, auto-created)
"""

import argparse
import csv
import json
import sqlite3
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("[ERROR] Install dependencies: pip install playwright rich sqlite-utils && playwright install chromium")
    raise

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich import print as rprint
    RICH = True
except ImportError:
    RICH = False

console = Console() if RICH else None

# ── Broker Registry ───────────────────────────────────────────────────────────
BROKERS = [
    # HIGH priority (recruiter-facing, heavily scraped)
    {"name": "ZoomInfo",             "category": "B2B/Recruiter",   "priority": "HIGH",
     "search_url": "https://www.zoominfo.com/person/{name_slug}",
     "optout_url": "https://www.zoominfo.com/about/privacy/privacy-request",
     "detect_selectors": [".profile-section", ".person-details", "h1.name"]},

    {"name": "Spokeo",               "category": "People Search",   "priority": "HIGH",
     "search_url": "https://www.spokeo.com/{name_slug}",
     "optout_url": "https://www.spokeo.com/optout",
     "detect_selectors": [".result-name", ".person-card", ".summary-section"]},

    {"name": "BeenVerified",         "category": "People Search",   "priority": "HIGH",
     "search_url": "https://www.beenverified.com/people/{name_slug}/",
     "optout_url": "https://www.beenverified.com/app/optout/search",
     "detect_selectors": [".bv-person-name", ".report-person", ".person-listing"]},

    {"name": "Whitepages",           "category": "People Search",   "priority": "HIGH",
     "search_url": "https://www.whitepages.com/name/{name_slug}",
     "optout_url": "https://www.whitepages.com/suppression-requests",
     "detect_selectors": [".wg-identity", ".profile-header", ".person-name"]},

    {"name": "Intelius",             "category": "People Search",   "priority": "HIGH",
     "search_url": "https://www.intelius.com/people/{name_slug}/",
     "optout_url": "https://www.intelius.com/opt-out",
     "detect_selectors": [".person-card", ".result-header", ".report-preview"]},

    {"name": "Radaris",              "category": "People Search",   "priority": "HIGH",
     "search_url": "https://radaris.com/p/{name_slug}/",
     "optout_url": "https://radaris.com/page/how-to-remove",
     "detect_selectors": [".person-name", ".search-result", ".profile-info"]},

    {"name": "InstantCheckmate",     "category": "Background",      "priority": "HIGH",
     "search_url": "https://www.instantcheckmate.com/people/{name_slug}/",
     "optout_url": "https://www.instantcheckmate.com/opt-out/",
     "detect_selectors": [".person-result", ".profile-card", ".report-header"]},

    {"name": "TruthFinder",          "category": "Background",      "priority": "HIGH",
     "search_url": "https://www.truthfinder.com/people/{name_slug}/",
     "optout_url": "https://www.truthfinder.com/opt-out/",
     "detect_selectors": [".person-card", ".result-preview", ".profile-name"]},

    {"name": "Acxiom",              "category": "Data Aggregator",  "priority": "HIGH",
     "search_url": "https://isapps.acxiom.com/optout/optout.aspx",
     "optout_url": "https://www.acxiom.com/optout/",
     "detect_selectors": [".opt-out-form", "input[name='email']"]},

    {"name": "MyLife",               "category": "Reputation",      "priority": "HIGH",
     "search_url": "https://www.mylife.com/{name_slug}",
     "optout_url": "https://www.mylife.com/privacy-policy/index.pubview",
     "detect_selectors": [".profile-name", ".person-reputation", ".person-overview"]},

    # MED priority
    {"name": "FastPeopleSearch",     "category": "People Search",   "priority": "MED",
     "search_url": "https://www.fastpeoplesearch.com/name/{name_slug}",
     "optout_url": "https://www.fastpeoplesearch.com/removal",
     "detect_selectors": [".card-block", ".person-info", ".result-card"]},

    {"name": "PeopleLooker",         "category": "People Search",   "priority": "MED",
     "search_url": "https://www.peoplelooker.com/find/people/{name_slug}",
     "optout_url": "https://www.peoplelooker.com/opt-out",
     "detect_selectors": [".person-result", ".listing-name", ".result-section"]},

    {"name": "USSearch",             "category": "People Search",   "priority": "MED",
     "search_url": "https://www.ussearch.com/search/people/results/?name={name_slug}",
     "optout_url": "https://www.ussearch.com/opt-out/",
     "detect_selectors": [".person-card", ".result-name", ".search-result"]},

    {"name": "PublicRecordsNow",     "category": "Public Records",  "priority": "MED",
     "search_url": "https://www.publicrecordsnow.com/people/search?name={name_slug}",
     "optout_url": "https://www.publicrecordsnow.com/static/view/optout",
     "detect_selectors": [".person-listing", ".result-card", ".record-preview"]},

    {"name": "CoreLogic",            "category": "Background",      "priority": "MED",
     "search_url": "https://www.corelogic.com/",
     "optout_url": "https://www.corelogic.com/privacy-consumer-opt-out/",
     "detect_selectors": [".opt-out-form", ".privacy-form"]},

    {"name": "Epsilon",              "category": "Data Aggregator", "priority": "MED",
     "search_url": "https://www.epsilon.com/us/privacy-policy/data-optout",
     "optout_url": "https://www.epsilon.com/us/privacy-policy/data-optout",
     "detect_selectors": [".optout-form", "input[type='email']"]},

    {"name": "PeopleFinder",         "category": "People Search",   "priority": "MED",
     "search_url": "https://www.peoplefinders.com/people/{name_slug}",
     "optout_url": "https://www.peoplefinders.com/opt-out",
     "detect_selectors": [".person-card", ".result-name", ".listing-card"]},

    {"name": "Pipl",                 "category": "B2B/Recruiter",   "priority": "MED",
     "search_url": "https://pipl.com/search/?q={name_slug}",
     "optout_url": "https://pipl.com/privacy/",
     "detect_selectors": [".search-result", ".person-info", ".profile-details"]},

    # LOW priority
    {"name": "Nuwber",               "category": "People Search",   "priority": "LOW",
     "search_url": "https://nuwber.com/search?name={name_slug}",
     "optout_url": "https://nuwber.com/removal/link",
     "detect_selectors": [".person-card", ".result-name"]},

    {"name": "CheckPeople",          "category": "Background",      "priority": "LOW",
     "search_url": "https://checkpeople.com/opt-out",
     "optout_url": "https://checkpeople.com/opt-out",
     "detect_selectors": [".opt-out-form", "input[name='firstName']"]},

    {"name": "CyberBackgroundChecks","category": "Background",      "priority": "LOW",
     "search_url": "https://www.cyberbackgroundchecks.com/people/{name_slug}",
     "optout_url": "https://www.cyberbackgroundchecks.com/removal",
     "detect_selectors": [".person-listing", ".result-item"]},

    {"name": "411.com",              "category": "People Search",   "priority": "LOW",
     "search_url": "https://www.411.com/name/{name_slug}",
     "optout_url": "https://www.411.com/privacy/request",
     "detect_selectors": [".person-result", ".listing"]},

    {"name": "AnyWho",               "category": "People Search",   "priority": "LOW",
     "search_url": "https://www.anywho.com/people/{name_slug}",
     "optout_url": "https://www.anywho.com/privacy",
     "detect_selectors": [".person-result", ".listing-card"]},

    {"name": "Addresses.com",        "category": "People Search",   "priority": "LOW",
     "search_url": "https://www.addresses.com/people/{name_slug}",
     "optout_url": "https://www.addresses.com/optout.php",
     "detect_selectors": [".result-card", ".person-info"]},

    {"name": "ClustrMaps",           "category": "People Search",   "priority": "LOW",
     "search_url": "https://clustrmaps.com/person/{name_slug}",
     "optout_url": "https://clustrmaps.com/bl/opt-out",
     "detect_selectors": [".person-details", ".profile-card"]},

    {"name": "Xlek",                 "category": "People Search",   "priority": "LOW",
     "search_url": "https://www.xlek.com/search?name={name_slug}",
     "optout_url": "https://www.xlek.com/optout.php",
     "detect_selectors": [".result-row", ".person-listing"]},

    {"name": "PrivateEye",           "category": "People Search",   "priority": "LOW",
     "search_url": "https://www.privateeye.com/search?name={name_slug}",
     "optout_url": "https://www.privateeye.com/static/view/optout/",
     "detect_selectors": [".person-card", ".result-preview"]},

    {"name": "Classmates",           "category": "Social",          "priority": "LOW",
     "search_url": "https://www.classmates.com/siteui/search/people?name={name_slug}",
     "optout_url": "https://www.classmates.com/siteui/privacy/",
     "detect_selectors": [".profile-card", ".member-name"]},

    {"name": "LexisNexis",           "category": "Data Aggregator", "priority": "HIGH",
     "search_url": "https://optout.lexisnexis.com/",
     "optout_url": "https://optout.lexisnexis.com/",
     "detect_selectors": ["form", "input[type='text']"]},

    {"name": "Experian",             "category": "Credit/Marketing","priority": "MED",
     "search_url": "https://www.experian.com/privacy/opting-out-preapproved-offers.html",
     "optout_url": "https://www.experian.com/privacy/opting-out-preapproved-offers.html",
     "detect_selectors": ["form", ".opt-out-section"]},
]


# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = Path("brokerscan.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date   TEXT NOT NULL,
            profile     TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id     INTEGER REFERENCES scans(id),
            broker      TEXT NOT NULL,
            category    TEXT,
            priority    TEXT,
            status      TEXT NOT NULL,
            optout_url  TEXT,
            checked_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_scan(conn, profile: dict) -> int:
    cur = conn.execute(
        "INSERT INTO scans (scan_date, profile) VALUES (?, ?)",
        (datetime.now().isoformat(), json.dumps(profile))
    )
    conn.commit()
    return cur.lastrowid


def save_result(conn, scan_id: int, broker: dict, status: str):
    conn.execute(
        """INSERT INTO results (scan_id, broker, category, priority, status, optout_url, checked_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (scan_id, broker["name"], broker["category"], broker["priority"],
         status, broker["optout_url"], datetime.now().isoformat())
    )
    conn.commit()


# ── Detection ─────────────────────────────────────────────────────────────────
def name_to_slug(name: str) -> str:
    """'John Doe' → 'john-doe'"""
    return name.lower().replace(" ", "-")


def check_broker(page, broker: dict, name: str, city: str) -> str:
    """
    Returns: 'FOUND' | 'CLEAN' | 'BLOCKED' | 'ERROR'

    Strategy:
    1. Navigate to the search URL with the name slug
    2. Look for result selectors that indicate a listing exists
    3. Check page text for name + city combo as secondary signal
    """
    slug = name_to_slug(name)
    url  = broker["search_url"].replace("{name_slug}", slug)
    first_name = name.split()[0].lower() if name.split() else ""
    city_lower = city.lower()

    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        # Random delay to avoid rate-limiting
        time.sleep(random.uniform(1.5, 3.5))

        # Check for CAPTCHA / block indicators
        page_text = page.content().lower()
        if any(x in page_text for x in ["captcha", "cf-challenge", "robot", "access denied", "403 forbidden"]):
            return "BLOCKED"

        # Check CSS selectors for result elements
        for selector in broker.get("detect_selectors", []):
            try:
                if page.query_selector(selector):
                    # Confirm name appears in result context
                    elem = page.query_selector(selector)
                    if elem:
                        elem_text = elem.inner_text().lower()
                        if first_name in elem_text or city_lower in elem_text:
                            return "FOUND"
            except Exception:
                continue

        # Secondary: full page text check
        if first_name in page_text and city_lower in page_text:
            return "FOUND"

        return "CLEAN"

    except PWTimeout:
        return "ERROR"
    except Exception as e:
        return "ERROR"


# ── Output helpers ────────────────────────────────────────────────────────────
STATUS_COLOR = {"FOUND": "bold yellow", "CLEAN": "green", "BLOCKED": "dim", "ERROR": "red"}

def print_result(broker_name: str, status: str, optout: str):
    if RICH:
        color = STATUS_COLOR.get(status, "white")
        icon  = {"FOUND": "⚠", "CLEAN": "✓", "BLOCKED": "⊘", "ERROR": "✗"}.get(status, "?")
        console.print(f"  [{color}]{icon} {broker_name:<28}[/{color}] [{status}]  {optout}")
    else:
        print(f"  [{status}] {broker_name} — {optout}")


def print_summary(results: list):
    found   = [r for r in results if r["status"] == "FOUND"]
    clean   = [r for r in results if r["status"] == "CLEAN"]
    blocked = [r for r in results if r["status"] == "BLOCKED"]
    errors  = [r for r in results if r["status"] == "ERROR"]

    if RICH:
        console.rule("[bold]Scan Complete")
        console.print(f"\n  [bold yellow]Exposed  : {len(found)}")
        console.print(f"  [green]Clean    : {len(clean)}")
        console.print(f"  [dim]Blocked  : {len(blocked)}  (CAPTCHA/rate-limited)")
        console.print(f"  [red]Errors   : {len(errors)}")

        if found:
            console.print("\n[bold yellow]⚠  Priority opt-outs:[/bold yellow]")
            high = [r for r in found if r["priority"] == "HIGH"]
            for r in high:
                console.print(f"  → {r['broker']:<28} {r['optout_url']}")
    else:
        print(f"\n=== SCAN COMPLETE ===")
        print(f"Exposed: {len(found)} | Clean: {len(clean)} | Blocked: {len(blocked)} | Errors: {len(errors)}")


def export_csv(results: list, path: str):
    fields = ["broker", "category", "priority", "status", "optout_url", "checked_at"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    print(f"\n  → Exported to {path}")


def get_due_rescan(conn, days: int = 90) -> list:
    """Return brokers where last scan was >N days ago or never scanned."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT broker FROM results
        GROUP BY broker
        HAVING MAX(checked_at) < ?
    """, (cutoff,)).fetchall()
    scanned = {r[0] for r in rows}
    all_names = {b["name"] for b in BROKERS}
    unscanned = all_names - scanned
    due = list(scanned | unscanned)
    return [b for b in BROKERS if b["name"] in due]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="BrokerScan — Data broker exposure scanner")
    parser.add_argument("--name",     required=True,  help="Full name, e.g. 'John Doe'")
    parser.add_argument("--city",     required=True,  help="City, e.g. 'Miami'")
    parser.add_argument("--state",    default="",     help="State abbreviation, e.g. 'FL'")
    parser.add_argument("--email",    default="",     help="Email address")
    parser.add_argument("--phone",    default="",     help="Phone number")
    parser.add_argument("--export",   default="",     help="Export results to CSV path")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
    parser.add_argument("--priority", choices=["HIGH", "MED", "LOW", "ALL"], default="ALL",
                        help="Only scan brokers of this priority level")
    parser.add_argument("--due-only", action="store_true",
                        help="Only scan brokers due for re-check (>90 days)")
    args = parser.parse_args()

    profile = {"name": args.name, "city": args.city, "state": args.state,
               "email": args.email, "phone": args.phone}

    conn    = init_db()
    scan_id = save_scan(conn, profile)

    brokers = BROKERS
    if args.priority != "ALL":
        brokers = [b for b in brokers if b["priority"] == args.priority]
    if args.due_only:
        due = get_due_rescan(conn)
        due_names = {b["name"] for b in due}
        brokers = [b for b in brokers if b["name"] in due_names]

    if RICH:
        console.rule("[bold]BrokerScan")
        console.print(f"  Profile : [bold]{args.name}[/bold] / {args.city}, {args.state}")
        console.print(f"  Brokers : {len(brokers)}  |  Scan ID: {scan_id}\n")

    scan_results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        page = context.new_page()
        # Mask webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for i, broker in enumerate(brokers, 1):
            if RICH:
                console.print(f"  [{i:02}/{len(brokers):02}] Checking {broker['name']}...", end="")
            else:
                print(f"[{i:02}/{len(brokers):02}] {broker['name']}...", end=" ", flush=True)

            status = check_broker(page, broker, args.name, args.city)
            save_result(conn, scan_id, broker, status)

            row = {**broker, "status": status, "checked_at": datetime.now().isoformat()}
            scan_results.append(row)

            if RICH:
                console.print(f"\r", end="")
            print_result(broker["name"], status, broker["optout_url"])

            # Polite delay between sites
            time.sleep(random.uniform(2, 4))

        browser.close()

    print_summary(scan_results)

    if args.export:
        export_csv(scan_results, args.export)

    conn.close()
    return scan_results


if __name__ == "__main__":
    main()
