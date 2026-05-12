#!/usr/bin/env python3
"""
MiRealSource agent enrichment script.

Usage:
    python3 mirealsource_enrich.py                          # uses input.csv
    python3 mirealsource_enrich.py MyExport.csv             # custom input file
    python3 mirealsource_enrich.py MyExport.csv out.csv     # custom output file

Output: enriched_contacts.csv (or your custom output path)
"""

import csv
import re
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

# ── Paste your browser session cookies here ───────────────────────────────────
# To refresh: open mirealsource.com while logged in → DevTools → Application
# → Cookies → copy CFID, CFTOKEN, LOG_SESSION values below.
COOKIES = {
    "CFID":        "2213388",
    "CFTOKEN":     "f8d9ba5299d16243-F8CBB477-AF42-08E0-AD072387CA90FC9B",
    "LOG_SESSION": "1778542205654161",
    "NEWVISITOR":  "1",
}

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.mirealsource.com/realtors.cfm",
    "Cookie":          "; ".join(f"{k}={v}" for k, v in COOKIES.items()),
}

BASE_URL   = "https://www.mirealsource.com/realtors.cfm"
DELAY_SECS = 0.8   # polite delay between requests


# ── HTML parser ────────────────────────────────────────────────────────────────

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_cell = False
        self.rows = []
        self._row = []
        self._cell = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.in_cell = False
            self._row.append(" ".join(self._cell).strip())
        elif tag == "tr":
            if any(c.strip() for c in self._row):
                self.rows.append(self._row)

    def handle_data(self, data):
        if self.in_cell:
            t = data.strip()
            if t:
                self._cell.append(t)


# ── Network helpers ────────────────────────────────────────────────────────────

def fetch(url, params=None):
    full_url = url + ("?" + urlencode(params) if params else "")
    req = Request(full_url, headers=HEADERS)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        print(f"    HTTP {e.code}")
        return ""
    except URLError as e:
        print(f"    URL error: {e.reason}")
        return ""


def probe_form():
    """Fetch the search page once to discover ColdFusion field names."""
    print("Probing MiRealSource search form …")
    html = fetch(BASE_URL)
    if not html:
        print("  ✗ Could not reach MiRealSource — check cookies / network.")
        return None
    fields  = re.findall(r'<(?:input|select)[^>]+name=["\']([^"\']+)["\']', html, re.I)
    action  = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, re.I)
    print(f"  Fields: {fields}")
    print(f"  Action: {action.group(1) if action else 'same page'}")
    return html


# ── Search logic ───────────────────────────────────────────────────────────────

PARAM_VARIANTS = [
    lambda f, l: {"lastname": l, "firstname": f, "Submit": "Search"},
    lambda f, l: {"lastname": l, "Submit": "Search"},
    lambda f, l: {"lname": l, "fname": f, "Submit": "Search"},
    lambda f, l: {"agent_lastname": l, "agent_firstname": f, "Submit": "Search"},
    lambda f, l: {"last_name": l, "first_name": f, "Submit": "Search"},
    lambda f, l: {"searchlastname": l, "searchfirstname": f, "Submit": "Search"},
]


def search_agent(first, last):
    for build_params in PARAM_VARIANTS:
        html = fetch(BASE_URL, build_params(first, last))
        if not html:
            continue
        result = parse_html(html, first, last)
        if result:
            return result
    return None


def parse_html(html, first, last):
    parser = TableParser()
    parser.feed(html)

    matched_rows = [
        row for row in parser.rows
        if last.lower() in " ".join(row).lower()
        and first.lower() in " ".join(row).lower()
    ]

    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html)
    phones = re.findall(r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}', html)

    if matched_rows:
        return {"rows": matched_rows, "emails": emails, "phones": phones}

    if re.search(r'no.results|no.agents.found|0.results', html, re.I):
        return None

    if last.lower() in html.lower():
        return {"rows": [], "emails": emails, "phones": phones}

    return None


# ── Result extraction ──────────────────────────────────────────────────────────

def extract(contact, result):
    row = {
        "Contact Id":     contact.get("Contact Id", ""),
        "First Name":     contact.get("First Name", ""),
        "Last Name":      contact.get("Last Name", ""),
        "Phone":          contact.get("Phone", ""),
        "Existing Email": contact.get("Email", ""),
        "Business Name":  contact.get("Business Name", ""),
        "Full Address":   contact.get("Full Address", ""),
        "Tags":           contact.get("Tags", ""),
        "MRS Office":     "not found",
        "MRS Address":    "not found",
        "MRS Email":      "not found",
        "MRS Phone":      "not found",
        "MRS Notes":      "",
    }

    if not result:
        row["MRS Notes"] = "not found on MiRealSource"
        return row

    rows   = result.get("rows", [])
    emails = result.get("emails", [])
    phones = result.get("phones", [])

    if rows:
        best = rows[0]
        if len(best) > 1:
            row["MRS Office"]  = best[1]
        if len(best) > 2:
            row["MRS Address"] = best[2]
        for cell in best:
            if re.match(r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}', cell):
                row["MRS Phone"] = cell
                break
        for cell in best:
            if "@" in cell and "." in cell:
                row["MRS Email"] = cell
                break

    if row["MRS Email"] == "not found":
        for e in emails:
            if not re.match(r'^(info|admin|webmaster|noreply|support)@', e, re.I):
                row["MRS Email"] = e
                break

    if row["MRS Phone"] == "not found" and phones:
        row["MRS Phone"] = phones[0]

    return row


# ── CSV I/O ────────────────────────────────────────────────────────────────────

def load_contacts(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_results(path, rows):
    if not rows:
        print("No results to write.")
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    in_file  = sys.argv[1] if len(sys.argv) > 1 else "input.csv"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "enriched_contacts.csv"

    print("=" * 60)
    print("MiRealSource Contact Enrichment")
    print(f"  Input : {in_file}")
    print(f"  Output: {out_file}")
    print("=" * 60)

    try:
        contacts = load_contacts(in_file)
    except FileNotFoundError:
        print(f"\n✗ Input file not found: {in_file}")
        print("  Place your EchoDesk CSV export in the same folder as this")
        print("  script and run:  python3 mirealsource_enrich.py YourFile.csv")
        sys.exit(1)

    print(f"\nLoaded {len(contacts)} contacts.\n")
    probe_form()
    print()

    results = []
    found_count = 0

    for i, contact in enumerate(contacts, 1):
        first = contact.get("First Name", "").strip()
        last  = contact.get("Last Name", "").strip()
        name  = f"{first} {last}".strip()

        if not first and not last:
            print(f"[{i:03d}/{len(contacts)}] Skipping — no name")
            results.append(extract(contact, None))
            continue

        print(f"[{i:03d}/{len(contacts)}] {name}")
        result  = search_agent(first, last)
        enriched = extract(contact, result)
        results.append(enriched)

        if result:
            found_count += 1
            print(f"  ✓  email={enriched['MRS Email']}  office={enriched['MRS Office']}")
        else:
            print(f"  –  not found")

        time.sleep(DELAY_SECS)

    write_results(out_file, results)
    print(f"\n{'='*60}")
    print(f"Done.  {found_count}/{len(contacts)} enriched from MiRealSource.")
    print(f"Saved → {out_file}")


if __name__ == "__main__":
    main()
