#!/usr/bin/env python3
"""
MiRealSource agent enrichment script.
Run locally: python3 mirealsource_enrich.py
Outputs: enriched_contacts.csv
"""

import csv
import re
import time
import json
from urllib.parse import urlencode, quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

# ── Session cookies from your browser ─────────────────────────────────────────
COOKIES = {
    "CFID": "2213388",
    "CFTOKEN": "f8d9ba5299d16243-F8CBB477-AF42-08E0-AD072387CA90FC9B",
    "LOG_SESSION": "1778542205654161",
    "NEWVISITOR": "1",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.mirealsource.com/realtors.cfm",
    "Cookie": "; ".join(f"{k}={v}" for k, v in COOKIES.items()),
}

BASE_URL = "https://www.mirealsource.com/realtors.cfm"

# ── Contact list ───────────────────────────────────────────────────────────────
CONTACTS = [
    {"id": "GdFQ4M4MBmHn7ZkCePp4", "first": "Lauren",        "last": "Fortinberry",  "phone": "+12482746556", "email": "lauren.fortinberry@cbrealty.com"},
    {"id": "5MogfPfITdI4qEV5mcB5", "first": "Lonette",       "last": "Blackburn",    "phone": "+12488427575", "email": "scott@scottsowles.com"},
    {"id": "vjmBENaCKPGwVRPwTUzC", "first": "Suzanne",       "last": "Mishler",      "phone": "+15172812862", "email": "smishler@cb-hb.com"},
    {"id": "1rGgOeQz5zn6s6BaWubC", "first": "Carol",         "last": "Ray",          "phone": "+18102650206", "email": "cray@bhhsmi.com"},
    {"id": "oHvAObMWmEQ4yTKJJuQo", "first": "Gary",          "last": "Hobson",       "phone": "+18102508347", "email": "gary@garyhobsonhomes.com"},
    {"id": "scxReeTbbRae1XArXo3L", "first": "Danny",         "last": "Dedic",        "phone": "+15868556672", "email": "dannydedic@kw.com"},
    {"id": "Rnq7dtstpyf6s8lb1MJD", "first": "Amy",           "last": "Martin",       "phone": "+15862424163", "email": "amy.martin@remax.net"},
    {"id": "T76QYzppftFf7hxz8QNq", "first": "Casey",         "last": "Williams",     "phone": "+15867095386", "email": "casey@coulterrealestate.com"},
    {"id": "sQXzAjbtXlt9XZWeZgDP", "first": "Savannah",      "last": "Mcfarlin",     "phone": "+15177757475", "email": "savannahkatie@kw.com"},
    {"id": "bfDksOINjJhebU43O8Hi", "first": "Melissa",       "last": "Itsell",       "phone": "+15178816277", "email": "melissaitsell@cb-hb.com"},
    {"id": "TjqoRFQ6WeRz3KY3u7Mz", "first": "Heaven",        "last": "Misale",       "phone": "+18102882921", "email": "heaven@riserealtymi.com"},
    {"id": "Fc81wsygY2yMUCTdPfUJ", "first": "Jim",           "last": "Miller",       "phone": "+18109223187", "email": "jimmiller@remax.net"},
    {"id": "SryT34wIpKqmhOGLIUAJ", "first": "Shayla",        "last": "Haboosh",      "phone": "+12489880366", "email": "shayla@anthonydjon.com"},
    {"id": "hPHm61b1Y1FCPTSkFFEX", "first": "Darrin",        "last": "Denha",        "phone": "+12485900800", "email": "darrindenha@kw.com"},
    {"id": "MMfSEWGK1KKbDJyQ1hEg", "first": "Debra",         "last": "Katz",         "phone": "+12484216751", "email": "debrakatz@kw.com"},
    {"id": "Rjg2tqwjbU20QwcClTD5", "first": "Brystol",       "last": "Rumschlag",    "phone": "+18106180209", "email": "brystolr@kwglover.com"},
    {"id": "OdMF0lf2OlJkSCbzxqN8", "first": "Nicole",        "last": "Rumbold",      "phone": "+18108369110", "email": "nicolegohnrumbold@gmail.com"},
    {"id": "EoYkye2wc2GyrRNbsoGs", "first": "Jen",           "last": "Rygalski",     "phone": "+14197083689", "email": "jen@refacmi.com"},
    {"id": "t11LvcCkvKWTclB0aZSu", "first": "Robert",        "last": "Bass",         "phone": "+12487241234", "email": "robertbass@nationalrealtycenters.com"},
    {"id": "vpOCoGqIWz7n7VQJcuNl", "first": "Sean",          "last": "Affrica",      "phone": "+18105696531", "email": "sean@seanaffrica.com"},
    {"id": "w6m7dLUfwBaq3rjaQEIg", "first": "Katie",         "last": "White",        "phone": "+18104447919", "email": "kate@katejwhite.com"},
    {"id": "PWCfRbLUWZSEGvEHrtWT", "first": "Jamie",         "last": "Rodriguez",    "phone": "+18105773459", "email": "jamiemrodriguez@kw.com"},
    {"id": "6j3u3mYoxVfTuwr9j0fU", "first": "Scott",         "last": "Duncan",       "phone": "+18055877697", "email": "scottduncan@kw.com"},
    {"id": "JKZQF9CzbqDLS1Kfaujt", "first": "Renae",         "last": "Smith",        "phone": "+19364994815", "email": "renae.smith@cbunited.com"},
    {"id": "BWL9UTQ7EoigzST9OYYu", "first": "Angela",        "last": "Aronson",      "phone": "+15862164349", "email": "aaronson@cbwm.com"},
    {"id": "AkGqviqshAbQrx6uGC95", "first": "Patty",         "last": "Roberge",      "phone": "+12485053352", "email": "proberge@cbwm.com"},
    {"id": "BS7swsV41L6tDqPJzIRb", "first": "Cindy",         "last": "Mastin",       "phone": "+12488544663", "email": "cmastin@kw.com"},
    {"id": "o0M0ymUN3Dy8Sq2H5sXz", "first": "Benny",         "last": "Margolis",     "phone": "+17349855091", "email": "bmargolis@realestateone.com"},
    {"id": "RSUcFGuwxpHOCeBSWUlT", "first": "Susheilla",     "last": "Mehta",        "phone": "+12488408714", "email": "su.mehta@realliving.com"},
    {"id": "NQetGdkK0mqfo8RIlviN", "first": "Ryan",          "last": "Lonsway",      "phone": "+12487657691", "email": "rlonsway@wsrealtor.com"},
    {"id": "3R5YgPnO43mjC9D2Zq15", "first": "Kevin",         "last": "Paton",        "phone": "+15862921770", "email": "kpaton@cbwm.com"},
    {"id": "u46iIhOhjmY5lumlADpj", "first": "Miranda",       "last": "Moore",        "phone": "+16162285654", "email": "miranda@ensleyteam.com"},
    {"id": "NvxJ0AcHDfgOrh1OenIe", "first": "Scott",         "last": "Levine",       "phone": "+12487605174", "email": "scott@maxbroock.com"},
    {"id": "QuhlK3N4Cf1iNeli4e3E", "first": "Darren",        "last": "Peterfi",      "phone": "+18104984016", "email": "darren@pcteamsells.com"},
    {"id": "ISbsASEtjkM77u0Clr2e", "first": "Shron",         "last": "Nathan",       "phone": "+15177061181", "email": "snathan@exitgl.com"},
    {"id": "wTjvtCYEDz9zoMIeO6HB", "first": "Bradley",       "last": "Yeokum",       "phone": "+12484209671", "email": "brad@yeokumhomes.com"},
    {"id": "oq753G8dEYLZgUegmYKi", "first": "Terence",       "last": "Frewen",       "phone": "+15172564321", "email": "tfrewen@coldwellbanker.com"},
    {"id": "g76ymS50t2UVYcvWoEfO", "first": "Danny",         "last": "Gossman",      "phone": "+15868715914", "email": "d.gossman@innetworkrealestate.com"},
    {"id": "4hbsdMoovx8ap9awgX6o", "first": "Stephen",       "last": "Wilhelm",      "phone": "+18102406138", "email": "stephen.wilhelm@realtyexecutives.com"},
    {"id": "UHOooMg71d2YIJAh4CMI", "first": "Sean",          "last": "Lax",          "phone": "+17024826142", "email": "homes@pcteamsells.com"},
    {"id": "u79uwZeJpYfKcSaOexxB", "first": "Kimberly",      "last": "Suozzi",       "phone": "+18104880085", "email": "coveragerealty@yahoo.com"},
    {"id": "XFQOh2WV7wqVLHqLgrb5", "first": "Miriam",        "last": "Olsen",        "phone": "+15179805547", "email": "miriamo@cb-hb.com"},
    {"id": "A2nUXhWTjw8ORFeUu4Wf", "first": "Stacie",        "last": "Neros",        "phone": "+15178962025", "email": "stacieneros@kw.com"},
    {"id": "j5ESTtw2D0sxky46yr5z", "first": "Kyle",          "last": "Raup",         "phone": "+18105133417", "email": "kyle.raup@century21.com"},
    {"id": "bvqx9ziDnK2I2k2b5wu9", "first": "Sean",          "last": "Pincombe",     "phone": "+12488727422", "email": "spincombe@realestateone.com"},
    {"id": "BysOfrFd4RtiqAGdLKXY", "first": "Kristin",       "last": "Krieger",      "phone": "+15867471551", "email": "kristin.krieger@coldwellbanker.com"},
    {"id": "rKvvcxD1biavcQIOZaIm", "first": "Janine",        "last": "Grillo",       "phone": "+15865315038", "email": "janinegrillo@kw.com"},
    {"id": "zEjXf4MSePn2eyW8Zmfp", "first": "Missy",         "last": "Ludd",         "phone": "+12482068383", "email": "missyludd@howardhanna.com"},
    {"id": "80PBM9dBvNKAptzgFPha", "first": "Anthony",       "last": "Benedetto",    "phone": "+12486446300", "email": "gschultz@cbwm.com"},
    {"id": "tcFuubSBxmp1G774YkEI", "first": "Jeff",          "last": "Glover",       "phone": "+12487195292", "email": "jgaleads@kwglover.com"},
]


class TableParser(HTMLParser):
    """Extracts text rows from HTML tables."""
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.in_th = False
        self.rows = []
        self._current_row = []
        self._current_cell = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self.in_td = True
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.in_td = False
            self._current_row.append(" ".join(self._current_cell).strip())
        elif tag == "tr":
            if any(c.strip() for c in self._current_row):
                self.rows.append(self._current_row)

    def handle_data(self, data):
        if self.in_td:
            text = data.strip()
            if text:
                self._current_cell.append(text)


def fetch(url, params=None):
    if params:
        url = url + "?" + urlencode(params)
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        print(f"  HTTP {e.code} for {url}")
        return ""
    except URLError as e:
        print(f"  URL error for {url}: {e.reason}")
        return ""


def probe_form():
    """Fetch the search page to discover form field names."""
    print("Probing MiRealSource search form...")
    html = fetch(BASE_URL)
    if not html:
        return None

    # Find all <input> and <select> field names
    fields = re.findall(r'<(?:input|select)[^>]+name=["\']([^"\']+)["\']', html, re.I)
    print(f"  Form fields found: {fields}")

    # Look for the form action
    action = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, re.I)
    print(f"  Form action: {action.group(1) if action else 'none (same page)'}")

    return html


def search_agent(first, last):
    """Try several search strategies for an agent name."""
    results = []

    # Strategy 1: last name search
    params = {"lastname": last, "firstname": first, "Submit": "Search"}
    html = fetch(BASE_URL, params)
    if html:
        results = parse_results(html, first, last)

    # Strategy 2: last name only if no results
    if not results:
        params = {"lastname": last, "Submit": "Search"}
        html = fetch(BASE_URL, params)
        if html:
            results = parse_results(html, first, last)

    # Strategy 3: common ColdFusion search param names
    if not results:
        for param_set in [
            {"lname": last, "fname": first},
            {"agent_lastname": last, "agent_firstname": first},
            {"searchlastname": last, "searchfirstname": first},
            {"last_name": last, "first_name": first},
        ]:
            param_set["Submit"] = "Search"
            html = fetch(BASE_URL, param_set)
            if html:
                results = parse_results(html, first, last)
                if results:
                    break

    return results


def parse_results(html, first, last):
    """Extract agent rows from HTML that match the target name."""
    matches = []

    # Try table parser
    parser = TableParser()
    parser.feed(html)

    target_name = f"{first} {last}".lower()

    for row in parser.rows:
        row_text = " ".join(row).lower()
        if last.lower() in row_text and first.lower() in row_text:
            matches.append(row)

    # Also try regex for common patterns: name, office, email, phone, address
    email_pattern = re.findall(
        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html
    )
    phone_pattern = re.findall(
        r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}', html
    )

    if matches:
        return {"rows": matches, "emails": email_pattern, "phones": phone_pattern}

    # If name not found in table rows, check if page has a "no results" indicator
    if re.search(r'no.results|no.agents.found|0.results', html, re.I):
        return None

    # Return raw emails/phones if name appears anywhere in the page
    if last.lower() in html.lower():
        return {"rows": [], "emails": email_pattern, "phones": phone_pattern}

    return None


def extract_best(contact, result):
    """Pick the best values from a search result."""
    enriched = {
        "Contact Id": contact["id"],
        "First Name": contact["first"],
        "Last Name": contact["last"],
        "Current Phone": contact["phone"],
        "Current Email": contact["email"],
        "MRS Office": "not found",
        "MRS Address": "not found",
        "MRS Email": "not found",
        "MRS Phone": "not found",
        "Notes": "",
    }

    if not result:
        enriched["Notes"] = "not found on MiRealSource"
        return enriched

    rows = result.get("rows", [])
    emails = result.get("emails", [])
    phones = result.get("phones", [])

    if rows:
        # Heuristic: columns are often Name, Office, City, Phone, Email
        best = rows[0]
        if len(best) >= 2:
            enriched["MRS Office"] = best[1] if len(best) > 1 else "not found"
        if len(best) >= 3:
            enriched["MRS Address"] = best[2] if len(best) > 2 else "not found"
        if len(best) >= 4:
            # Find the cell that looks like a phone
            for cell in best:
                if re.match(r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}', cell):
                    enriched["MRS Phone"] = cell
                    break
        for cell in best:
            if "@" in cell and "." in cell:
                enriched["MRS Email"] = cell
                break

    # Supplement with regex-extracted emails/phones
    if enriched["MRS Email"] == "not found" and emails:
        # Prefer emails that don't look like the webmaster/info address
        for e in emails:
            if not re.match(r'^(info|admin|webmaster|noreply|support)@', e, re.I):
                enriched["MRS Email"] = e
                break

    if enriched["MRS Phone"] == "not found" and phones:
        enriched["MRS Phone"] = phones[0]

    return enriched


def main():
    print("=" * 60)
    print("MiRealSource Agent Enrichment")
    print("=" * 60)

    # Probe the form first
    probe_html = probe_form()

    results = []
    for i, contact in enumerate(CONTACTS, 1):
        name = f"{contact['first']} {contact['last']}"
        print(f"[{i:02d}/{len(CONTACTS)}] Searching: {name}")
        result = search_agent(contact["first"], contact["last"])
        enriched = extract_best(contact, result)
        results.append(enriched)
        if result:
            print(f"  ✓ Found — email: {enriched['MRS Email']}, office: {enriched['MRS Office']}")
        else:
            print(f"  ✗ Not found")
        time.sleep(0.8)  # be polite to the server

    # Write CSV
    out_file = "enriched_contacts.csv"
    fieldnames = [
        "Contact Id", "First Name", "Last Name",
        "Current Phone", "Current Email",
        "MRS Office", "MRS Address", "MRS Email", "MRS Phone", "Notes"
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    found = sum(1 for r in results if r["Notes"] != "not found on MiRealSource")
    print(f"\nDone. {found}/{len(results)} contacts enriched.")
    print(f"Output saved to: {out_file}")


if __name__ == "__main__":
    main()
