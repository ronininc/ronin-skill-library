#!/usr/bin/env python3
"""Track EXPANDING joint-venture / syndication real-estate investors in Arizona from their PUBLIC SEC
filings (Reg D **Form D** private-placement notices via EDGAR). This is a FORWARD signal: a Form D says
"we are raising capital to acquire" — with the PRINCIPALS NAMED and the OFFERING SIZE stated. Ranked by
capital still to deploy (offering - sold) = who is hungriest to buy next.

Why this is the right source for "known JV investors expanding per their filings":
  * Assessor data is BACKWARD (deals already closed). Form D is FORWARD (money being raised right now).
  * Form D lists RELATED PERSONS (Exec Officer / Director / Promoter) = a real human to reach, not an
    anonymous LLC shell. It also states total offering, amount sold, and minimum investment.
  * "Still raising" (amount_sold < total_offering) + a recent/amended filing = actively expanding.

HONESTY INVARIANTS (do not remove):
  * Source = SEC EDGAR full-text search (efts.sec.gov) + the filing's structured primary_doc.xml. Public,
    free. State filter is the FILER's principal-office state via `locationCodes=AZ` (the working param;
    singular `locationCode` is silently ignored). We DO NOT fabricate — every field is read from the XML.
  * Recall caveat: we net RE filers via real-estate query TERMS. A filer whose Form D never contains those
    words (e.g. labeled only "Residential"/"Commercial") can be missed. Use --all-az to scan every AZ
    Form D and filter by the XML industry group for full recall (slower: many more fetches).
  * Contactability: Form D gives the issuer's business address + named principals. It does NOT give phone
    numbers; never invent one. Reach via the entity address, the principals' names, or the SEC filing.
  * SEC asks for a descriptive User-Agent and <=10 req/s. We set a UA and sleep between fetches.

Usage:
  find_expanding_jv_investors.py [--start 2025-01-01] [--end today] [--max-issuers 150]
                                 [--terms "real estate,multifamily,apartment"] [--all-az] [--out out.csv]
"""
import argparse, csv, datetime as dt, json, re, sys, time, urllib.parse, urllib.request

FTS = "https://efts.sec.gov/LATEST/search-index"
ARCH = "https://www.sec.gov/Archives/edgar/data"
UA = {"User-Agent": "RoninLeadEngine leads@ronininc.org"}
RE_INDUSTRY = ("REAL ESTATE", "RESIDENTIAL", "COMMERCIAL", "CONSTRUCTION", "REIT")  # Form D "Real Estate" group


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def fts_page(term, state, start, end, frm):
    qs = {"forms": "D", "locationCodes": state, "startdt": start, "enddt": end, "from": str(frm)}
    if term: qs["q"] = f'"{term}"'
    return json.loads(_get(f"{FTS}?{urllib.parse.urlencode(qs)}"))


def collect(terms, state, start, end, page_cap=600):
    """Page EDGAR FTS across all query terms; dedup by CIK keeping the most-recent filing."""
    seen = {}
    for term in terms:
        frm, total = 0, None
        while frm < page_cap:
            d = fts_page(term, state, start, end, frm)
            h = d.get("hits", {}); hits = h.get("hits", [])
            if total is None: total = h.get("total", {}).get("value", 0)
            if not hits: break
            for x in hits:
                s = x.get("_source", {})
                cik = (s.get("ciks") or [""])[0]
                if not cik: continue
                rec = {"cik": cik, "id": x.get("_id", ""), "date": s.get("file_date", ""),
                       "name": (s.get("display_names") or ["?"])[0],
                       "ftype": (s.get("file_type") or (s.get("root_forms") or ["D"])[0])}
                cur = seen.get(cik)
                if not cur or rec["date"] > cur["date"]:
                    seen[cik] = rec
            frm += len(hits)
            if frm >= (total or 0): break
            time.sleep(0.12)
    return list(seen.values())


def tag(t):
    m = re.search(rf"<[^>]*{t}>(.*?)</[^>]*{t}>", XML, re.S); return (m.group(1).strip() if m else "")


def parse_formd(cik, acc_id):
    global XML
    acc, doc = acc_id.split(":") if ":" in acc_id else (acc_id, "primary_doc.xml")
    url = f"{ARCH}/{int(cik)}/{acc.replace('-','')}/{doc}"
    XML = _get(url).decode("utf-8", "replace")
    def blk(tag_):  # first block by tag name
        m = re.search(rf"<{tag_}>(.*?)</{tag_}>", XML, re.S); return m.group(1) if m else ""
    issuer = tag("entityName")
    city = tag("city"); state = tag("stateOrCountry") or tag("stateOrCountryDescription")
    industry = tag("industryGroupType")
    offering = tag("totalOfferingAmount"); sold = tag("totalAmountSold")
    minv = tag("minimumInvestmentAccepted"); etype = tag("entityTypeOtherDesc") or tag("entityType")
    # related persons -> "Name (Role)"
    ppl = []
    for rp in re.findall(r"<relatedPersonInfo>(.*?)</relatedPersonInfo>", XML, re.S):
        fn = re.search(r"<firstName>(.*?)</firstName>", rp); ln = re.search(r"<lastName>(.*?)</lastName>", rp)
        roles = re.findall(r"<relationship>(.*?)</relationship>", rp)
        nm = " ".join(p.group(1).strip() for p in (fn, ln) if p and p.group(1).strip())
        if nm: ppl.append(f"{nm} ({'/'.join(roles)})" if roles else nm)
    return {"issuer": issuer, "city": city.upper(), "state": state.upper(), "industry": industry,
            "offering": offering, "sold": sold, "min_invest": minv, "principals": "; ".join(ppl[:6]),
            "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}"}


def num(s):
    try: return float(s)
    except (TypeError, ValueError): return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--state", default="AZ")
    ap.add_argument("--max-issuers", type=int, default=150)
    ap.add_argument("--terms", default="real estate,multifamily,apartment",
                    help="RE query terms to net filers (comma-sep). Ignored with --all-az.")
    ap.add_argument("--all-az", action="store_true", help="scan ALL AZ Form D and keep RE by industry (slow)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    terms = [""] if a.all_az else [t.strip() for t in a.terms.split(",") if t.strip()]
    print(f"Collecting AZ Form D filings {a.start}..{a.end} (terms={terms or 'ALL'}) ...", file=sys.stderr)
    issuers = collect(terms, a.state, a.start, a.end)
    issuers.sort(key=lambda r: r["date"], reverse=True)
    print(f"  {len(issuers)} unique issuers; fetching Form D XML for up to {a.max_issuers} ...", file=sys.stderr)

    rows = []
    for r in issuers[:a.max_issuers]:
        try:
            info = parse_formd(r["cik"], r["id"])
        except Exception as e:
            print(f"  skip {r['name']}: {e}", file=sys.stderr); continue
        if a.all_az and not any(k in (info["industry"] or "").upper() for k in RE_INDUSTRY):
            continue  # industry-filter only needed when we didn't pre-filter by RE terms
        off, sold = num(info["offering"]), num(info["sold"])
        remaining = (off - sold) if (off is not None and sold is not None) else None
        pct = round(100 * sold / off, 1) if (off and sold is not None and off > 0) else None
        rows.append({**r, **info, "remaining": remaining, "pct_sold": pct})
        time.sleep(0.12)

    # rank: still-raising & most capital left to deploy first, then most recent filing
    def rank_key(x):
        rem = x["remaining"] if isinstance(x["remaining"], (int, float)) else -1
        return (rem, x["date"])
    rows.sort(key=rank_key, reverse=True)

    out = a.out or f"AZ_expanding_jv_investors_formD.csv"
    cols = ["rank", "issuer", "city", "state", "industry", "filing_type", "filing_date",
            "offering_amount", "amount_sold", "amount_remaining", "pct_sold", "min_investment",
            "principals", "cik", "filing_url"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for i, x in enumerate(rows, 1):
            w.writerow({"rank": i, "issuer": x["issuer"] or x["name"], "city": x["city"], "state": x["state"],
                        "industry": x["industry"], "filing_type": x["ftype"], "filing_date": x["date"],
                        "offering_amount": x["offering"], "amount_sold": x["sold"],
                        "amount_remaining": ("" if x["remaining"] is None else int(x["remaining"])),
                        "pct_sold": ("" if x["pct_sold"] is None else x["pct_sold"]),
                        "min_investment": x["min_invest"], "principals": x["principals"],
                        "cik": x["cik"], "filing_url": x["url"]})
    still = sum(1 for x in rows if isinstance(x["remaining"], (int, float)) and x["remaining"] > 0)
    print(f"WROTE {len(rows)} AZ real-estate JV/syndication issuers -> {out}  "
          f"({still} still actively raising capital)")


if __name__ == "__main__":
    main()
