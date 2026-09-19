#!/usr/bin/env python3
"""Find active real-estate cash-buyer / investor entities in Maricopa County (Phoenix metro) from the
PUBLIC Maricopa County Assessor ArcGIS parcel service. Ranked by RECENT single-family acquisitions
= who is actively buying now (the dispo-buyer "most active" signal).

HONESTY INVARIANTS (do not remove):
  * LLC-owned SFR portfolio + recent purchase is the accepted CASH-BUYER PROXY. The Assessor has NO
    mortgage field, so "cash" is NOT verified — never label these "verified cash".
  * Reachable channel = the owner MAILING ADDRESS (public record). NO phone numbers exist in this source;
    never fabricate one. Phones require skip-tracing (see SKILL.md enrichment ladder).
  * Maricopa County only. Other AZ counties (Pima, Pinal, ...) run separate assessors — not covered.
  * Grouped-stats paging on this service double-counts tied groups, so we fetch a SINGLE page ordered
    by count (top buyers sort to the top). recent<=total is enforced as an integrity guard.

Usage:
  find_buyers.py [--count 200] [--recent-years 3] [--puc 0131] [--out /path/to/out.csv]
"""
import argparse, csv, datetime as dt, json, re, sys, urllib.parse, urllib.request

URL = "https://gis.mcassessor.maricopa.gov/arcgis/rest/services/MaricopaDynamicQueryService/MapServer/3/query"
UA = {"User-Agent": "RoninLeadEngine/0.1 (+leads@ronininc.org)"}
INSTITUTIONAL = ("OPENDOOR", "OFFERPAD", "PROGRESS RESIDENTIAL", "INVITATION HOMES", "FIRSTKEY", "AMHERST",
                 "TRICON", "VINEBROOK", "HOME PARTNERS", "AMERICAN HOMES 4 RENT", "AMH ", "RH PARTNERS",
                 "MONTPELIER", "ARMM", "DOORS HOLDINGS", "PRNL", "ALTO ", "CBAR", "BORROWER", "SPE ",
                 "OWNERCO", "ASSET COMPANY", "2025-", "2024-", "HFS ASSET")


def q(where, group, limit=2000):
    """Single-page grouped COUNT query (no offset paging — it double-counts tied groups)."""
    body = urllib.parse.urlencode({
        "where": where,
        "outStatistics": json.dumps([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}]),
        "groupByFieldsForStatistics": group, "orderByFields": "n DESC",
        "resultRecordCount": str(limit), "f": "json",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=60) as r:
        d = json.load(r)
    if d.get("error"):
        print("Assessor API error:", d["error"], file=sys.stderr); sys.exit(1)
    return [f["attributes"] for f in d.get("features", [])]


def norm(s): return re.sub(r"\s+", " ", (s or "").strip()).upper()


def tier(owner, mail_state, total):
    if any(k in owner for k in INSTITUTIONAL): return "institutional"
    if mail_state and mail_state != "AZ": return "out-of-state fund"
    if total >= 150: return "large regional"
    return "local/regional"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--recent-years", type=int, default=3, help="acquisitions in the last N years count as 'active'")
    ap.add_argument("--puc", default="0131", help="Assessor property-use code (0131 = single-family residential)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    yr = dt.date.today().year
    years = [str(yr - i) for i in range(a.recent_years)]
    recent = "(" + " OR ".join(f"SALE_DATE LIKE '%{y}%'" for y in years) + ")"
    llc, sfr = "OWNER_NAME LIKE '%LLC%'", f"PUC='{a.puc}'"

    # 1) recent buys grouped with mailing address (sum distinct mailing rows per owner within one page)
    rec = {}
    for x in q(f"{llc} AND {sfr} AND {recent}", "OWNER_NAME,MAIL_ADDRESS,MAIL_CITY,MAIL_STATE,MAIL_ZIP"):
        o = norm(x.get("OWNER_NAME"))
        if not o: continue
        e = rec.setdefault(o, {"recent": 0, "mail": None, "mn": -1})
        n = int(x.get("n") or 0); e["recent"] += n
        if n > e["mn"]:
            e["mn"] = n
            e["mail"] = (norm(x.get("MAIL_ADDRESS")), norm(x.get("MAIL_CITY")), norm(x.get("MAIL_STATE")), norm(x.get("MAIL_ZIP")))
    # 2) all-time SFR portfolio per owner
    total = {norm(x.get("OWNER_NAME")): int(x.get("n") or 0) for x in q(f"{llc} AND {sfr}", "OWNER_NAME")}

    ranked = sorted(rec.items(), key=lambda kv: (kv[1]["recent"], total.get(kv[0], 0)), reverse=True)[:a.count]
    out = a.out or f"AZ_active_cash_buyers_top{a.count}_maricopa.csv"
    cols = ["rank", "entity", "recent_buys", "total_sfr_portfolio", "mailing_address", "mail_city",
            "mail_state", "mail_zip", "locale", "tier", "phone"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for i, (owner, e) in enumerate(ranked, 1):
            m = e["mail"] or ("", "", "", ""); st = m[2]
            tot = max(total.get(owner, 0), e["recent"])  # integrity: total >= recent
            w.writerow({"rank": i, "entity": owner, "recent_buys": e["recent"], "total_sfr_portfolio": tot,
                        "mailing_address": m[0], "mail_city": m[1], "mail_state": st, "mail_zip": m[3],
                        "locale": "AZ-local" if st == "AZ" else ("out-of-state" if st else "unknown"),
                        "tier": tier(owner, st, tot), "phone": ""})  # phone left blank — skip-trace, never faked
    az = sum(1 for _, e in ranked if (e["mail"] or ("", "", "", ""))[2] == "AZ")
    print(f"WROTE {len(ranked)} buyers -> {out}  ({az} AZ-local)  recent-buy range "
          f"{ranked[0][1]['recent']}..{ranked[-1][1]['recent']}")


if __name__ == "__main__":
    main()
