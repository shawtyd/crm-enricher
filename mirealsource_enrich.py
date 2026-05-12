#!/usr/bin/env python3
"""
MiRealSource agent enrichment script.

Usage:
    python3 mirealsource_enrich.py MyExport.csv             # enriches contacts
    python3 mirealsource_enrich.py MyExport.csv out.csv     # custom output path
    python3 mirealsource_enrich.py --probe                  # just show form fields

Output: enriched_contacts.csv (or your custom output path)
"""

import csv
import os
import re
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

# ── Paste your browser session cookies here ───────────────────────────────────
COOKIES = {
    "CFID":        "2213388",
    "CFTOKEN":     "f8d9ba5299d16243-F8CBB477-AF42-08E0-AD072387CA90FC9B",
    "LOG_SESSION": "1778542205654161",
    "NEWVISITOR":  "1",
}

BASE_URL   = "https://www.mirealsource.com/realtors.cfm"
DELAY_SECS = 1.0
DEBUG_DIR  = "mrs_debug"   # raw HTML responses saved here for inspection


def make_headers(extra=None):
    h = {
        "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         BASE_URL,
        "Cookie":          "; ".join(f"{k}={v}" for k, v in COOKIES.items()),
    }
    if extra:
        h.update(extra)
    return h


# ── HTML helpers ───────────────────────────────────────────────────────────────

class FormParser(HTMLParser):
    """Extracts the first <form> element's method, action, and field names."""
    def __init__(self):
        super().__init__()
        self.forms = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {
                "method": a.get("method", "get").upper(),
                "action": a.get("action", ""),
                "fields": [],
            }
        elif tag in ("input", "select", "textarea") and self._form is not None:
            name = a.get("name", "")
            val  = a.get("value", "")
            if name:
                self._form["fields"].append({"name": name, "value": val,
                                             "type": a.get("type", "text")})

    def handle_endtag(self, tag):
        if tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None


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
        if self.in_cell and data.strip():
            self._cell.append(data.strip())


# ── Network ────────────────────────────────────────────────────────────────────

def fetch_get(url, params=None, label=None):
    full_url = url + ("?" + urlencode(params) if params else "")
    req = Request(full_url, headers=make_headers())
    return _do_fetch(req, label)


def fetch_post(url, data, label=None):
    body = urlencode(data).encode("utf-8")
    req  = Request(url, data=body, headers=make_headers({
        "Content-Type": "application/x-www-form-urlencoded",
    }))
    return _do_fetch(req, label)


def _do_fetch(req, label=None):
    try:
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            if label:
                _save_debug(label, html)
            return html
    except HTTPError as e:
        print(f"    HTTP {e.code}")
        return ""
    except URLError as e:
        print(f"    URL error: {e.reason}")
        return ""


def _save_debug(label, html):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', label)[:60]
    path = os.path.join(DEBUG_DIR, safe + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ── Form discovery ─────────────────────────────────────────────────────────────

def probe_form():
    """
    Fetch the search page, parse the form, and return:
      { method, action, first_field, last_field, hidden_fields }
    Returns None if the page can't be reached.
    """
    print("Probing MiRealSource search form …")
    html = fetch_get(BASE_URL, label="probe")
    if not html:
        print("  ✗ Could not reach MiRealSource.")
        print("    → Check your cookies are fresh and you have internet access.")
        return None

    fp = FormParser()
    fp.feed(html)

    if not fp.forms:
        print("  ✗ No <form> found on the page.")
        print(f"    → Check {DEBUG_DIR}/probe.html to see what the server returned.")
        return None

    form = fp.forms[0]
    print(f"  Method : {form['method']}")
    print(f"  Action : {form['action'] or '(same page)'}")
    print(f"  Fields : {[f['name'] for f in form['fields']]}")

    # Find which fields look like first-name / last-name inputs
    first_field = _find_field(form["fields"], ["firstname","first_name","fname",
                                                "agent_firstname","searchfirstname",
                                                "f_name","agentfirst"])
    last_field  = _find_field(form["fields"], ["lastname","last_name","lname",
                                                "agent_lastname","searchlastname",
                                                "l_name","agentlast"])

    print(f"  First-name field: {first_field or '(not found — will try all guesses)'}")
    print(f"  Last-name  field: {last_field  or '(not found — will try all guesses)'}")

    hidden = {f["name"]: f["value"]
              for f in form["fields"]
              if f.get("type", "").lower() == "hidden"}

    action_url = form["action"] or BASE_URL
    if action_url and not action_url.startswith("http"):
        action_url = "https://www.mirealsource.com/" + action_url.lstrip("/")

    return {
        "method":      form["method"],
        "action":      action_url,
        "first_field": first_field,
        "last_field":  last_field,
        "hidden":      hidden,
        "all_fields":  form["fields"],
    }


def _find_field(fields, candidates):
    for candidate in candidates:
        for f in fields:
            if f["name"].lower() == candidate.lower():
                return f["name"]
    return None


# ── Search ─────────────────────────────────────────────────────────────────────

FALLBACK_FIRST_FIELDS = ["firstname","first_name","fname","agent_firstname","searchfirstname"]
FALLBACK_LAST_FIELDS  = ["lastname","last_name","lname","agent_lastname","searchlastname"]


def search_agent(first, last, form_info):
    method     = form_info["method"]      if form_info else "POST"
    action     = form_info["action"]      if form_info else BASE_URL
    ff         = form_info["first_field"] if form_info else None
    lf         = form_info["last_field"]  if form_info else None
    hidden     = form_info["hidden"]      if form_info else {}

    # Build a list of (first_key, last_key) combinations to try
    first_keys = [ff] if ff else FALLBACK_FIRST_FIELDS
    last_keys  = [lf] if lf else FALLBACK_LAST_FIELDS
    combos     = [(fk, lk) for fk in first_keys for lk in last_keys]

    label = f"{last}_{first}"

    for fk, lk in combos:
        params = dict(hidden)
        params[fk] = first
        params[lk] = last
        params["Submit"] = "Search"

        if method == "POST":
            html = fetch_post(action, params, label=label)
        else:
            html = fetch_get(action, params, label=label)

        if not html:
            continue

        result = parse_html(html, first, last)
        if result:
            return result

    return None


# ── Result parsing ─────────────────────────────────────────────────────────────

def parse_html(html, first, last):
    tp = TableParser()
    tp.feed(html)

    matched_rows = [
        row for row in tp.rows
        if last.lower() in " ".join(row).lower()
        and first.lower() in " ".join(row).lower()
    ]

    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html)
    phones = re.findall(r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}', html)

    if matched_rows:
        return {"rows": matched_rows, "emails": emails, "phones": phones}

    if re.search(r'no.?results|no.?agents.?found|0.?results', html, re.I):
        return None

    # Name present somewhere on page but not in a table row
    if last.lower() in html.lower():
        return {"rows": [], "emails": emails, "phones": phones}

    return None


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


# ── CSV helpers ────────────────────────────────────────────────────────────────

def load_contacts(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_results(path, rows):
    if not rows:
        print("No results to write.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if "--probe" in sys.argv:
        probe_form()
        print(f"\nRaw HTML saved to {DEBUG_DIR}/probe.html — open it to inspect the page.")
        return

    in_file  = next((a for a in sys.argv[1:] if not a.startswith("-")), "input.csv")
    out_file = sys.argv[sys.argv.index(in_file) + 1] \
               if sys.argv.index(in_file) + 1 < len(sys.argv) \
               and not sys.argv[sys.argv.index(in_file) + 1].startswith("-") \
               else "enriched_contacts.csv"

    print("=" * 60)
    print("MiRealSource Contact Enrichment")
    print(f"  Input : {in_file}")
    print(f"  Output: {out_file}")
    print(f"  Debug : {DEBUG_DIR}/  (raw HTML responses)")
    print("=" * 60 + "\n")

    try:
        contacts = load_contacts(in_file)
    except FileNotFoundError:
        print(f"✗ File not found: {in_file}")
        sys.exit(1)

    print(f"Loaded {len(contacts)} contacts.\n")

    form_info = probe_form()
    if not form_info:
        print("\n✗ Stopping — could not read the MiRealSource search form.")
        print(f"  Open {DEBUG_DIR}/probe.html to see what the server returned.")
        print("  If it shows a login page, your cookies have expired — grab fresh ones.")
        sys.exit(1)

    print()
    results     = []
    found_count = 0

    for i, contact in enumerate(contacts, 1):
        first = contact.get("First Name", "").strip()
        last  = contact.get("Last Name", "").strip()

        if not first and not last:
            print(f"[{i:03d}/{len(contacts)}] Skipping — no name")
            results.append(extract(contact, None))
            continue

        print(f"[{i:03d}/{len(contacts)}] {first} {last}")
        result   = search_agent(first, last, form_info)
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
    print(f"Done.  {found_count}/{len(contacts)} enriched.")
    print(f"Output → {out_file}")
    print(f"Debug  → {DEBUG_DIR}/  (open any .html file to inspect a response)")


if __name__ == "__main__":
    main()
