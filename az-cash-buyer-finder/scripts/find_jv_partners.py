#!/usr/bin/env python3
"""Find JOINT-VENTURE / deal-PARTNER prospects in Maricopa County (Phoenix metro) from the PUBLIC
Maricopa County Assessor ArcGIS parcel service. This is the PARTNER side, NOT the dispo-BUYER side.

A cash-buyer list wants BIG + PASSIVE (funds you SELL an assigned deal to). A JV list wants the OPPOSITE:
LOCAL + ACTIVE + HUMAN-SCALE operators you can actually partner with (co-wholesale, split a fee, one
brings the deal / one brings the buyer). So we reuse the buyer-finder's proven query mechanics but
INVERT the scoring: keep AZ-local, drop institutional funds, keep human-scale portfolios, and rank by
recent activity + velocity (recent buys / portfolio) = who is transacting NOW at a partner-able scale.

HONESTY INVARIANTS (do not remove):
  * This surfaces ACTIVE LOCAL INVESTOR-OPERATORS = realistic JV/deal partners. It does NOT "verify
    wholesalers": a pure wholesaler ASSIGNS before closing and never takes title, so they may not appear
    as an owner here at all. The true buy-AND-sell velocity signal lives in the COUNTY RECORDER
    grantor/grantee index (a different source). Say so.
  * Reachable channel = the owner MAILING ADDRESS (public record). NO phone numbers exist in this
    source; the phone column ships blank. Never fabricate a phone — that needs a real skip-trace.
  * Maricopa County only. Other AZ counties run separate assessors.
  * Single-page grouped COUNT queries (offset paging double-counts tied groups). recent<=total enforced.

Usage:
  find_jv_partners.py [--count 200] [--recent-years 3] [--puc 0131]
                      [--min-portfolio 2] [--max-portfolio 40] [--out /path/to/out.csv]
"""
import argparse, csv, datetime as dt, json, re, sys, urllib.parse, urllib.request

URL = "https://gis.mcassessor.maricopa.gov/arcgis/rest/services/MaricopaDynamicQueryService/MapServer/3/query"
UA = {"User-Agent": "RoninLeadEngine/0.1 (+leads@ronininc.org)"}
# Funds / iBuyers / institutional operators you can't JV with — excluded from a PARTNER list.
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


def jv_profile(total, velocity):
    """Describe the partner archetype from portfolio size + recent activity rate (honest labels)."""
    if velocity >= 0.5: return "hot operator (high turn)"      # buying fast relative to holdings = flip/partner-hungry
    if total <= 8:      return "emerging local operator"        # small + active = the classic JV partner
    return "established local operator"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--recent-years", type=int, default=3, help="acquisitions in the last N years = 'active'")
    ap.add_argument("--puc", default="0131", help="Assessor property-use code (0131 = single-family residential)")
    ap.add_argument("--min-portfolio", type=int, default=2, help="drop one-off owners below this (not real operators)")
    ap.add_argument("--max-portfolio", type=int, default=40, help="drop mega-portfolios above this (funds, not JV-able)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    yr = dt.date.today().year
    years = [str(yr - i) for i in range(a.recent_years)]
    recent = "(" + " OR ".join(f"SALE_DATE LIKE '%{y}%'" for y in years) + ")"
    llc, sfr = "OWNER_NAME LIKE '%LLC%'", f"PUC='{a.puc}'"

    # 1) recent buys per owner, with the mailing address (one page; sum distinct mailing rows per owner)
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

    # JV scope: AZ-local, non-institutional, human-scale portfolio, still active. Rank by recent activity
    # then velocity (partner-hungry), then keep smaller operators ahead of bigger ones.
    rows = []
    for owner, e in rec.items():
        st = (e["mail"] or ("", "", "", ""))[2]
        if st != "AZ": continue                                   # you JV locally
        if any(k in owner for k in INSTITUTIONAL): continue        # funds are dispo buyers, not JV partners
        tot = max(total.get(owner, 0), e["recent"])                # integrity: total >= recent
        if tot < a.min_portfolio or tot > a.max_portfolio: continue
        vel = round(e["recent"] / tot, 2) if tot else 0.0
        rows.append((owner, e, tot, vel))
    # recent DESC, velocity DESC, smaller portfolio first (more likely a hands-on partner, not a mini-fund)
    rows.sort(key=lambda r: (r[1]["recent"], r[3], -r[2]), reverse=True)
    ranked = rows[:a.count]

    out = a.out or f"AZ_jv_partners_top{a.count}_maricopa.csv"
    cols = ["rank", "entity", "recent_buys", "total_sfr_portfolio", "velocity", "jv_profile",
            "mailing_address", "mail_city", "mail_state", "mail_zip", "phone"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for i, (owner, e, tot, vel) in enumerate(ranked, 1):
            m = e["mail"] or ("", "", "", "")
            w.writerow({"rank": i, "entity": owner, "recent_buys": e["recent"], "total_sfr_portfolio": tot,
                        "velocity": vel, "jv_profile": jv_profile(tot, vel),
                        "mailing_address": m[0], "mail_city": m[1], "mail_state": m[2], "mail_zip": m[3],
                        "phone": ""})  # blank — skip-trace, never faked
    if ranked:
        print(f"WROTE {len(ranked)} JV prospects -> {out}  (all AZ-local, non-institutional, "
              f"portfolio {a.min_portfolio}-{a.max_portfolio})  recent-buy range "
              f"{ranked[0][1]['recent']}..{ranked[-1][1]['recent']}")
    else:
        print("No rows matched the JV scope — widen --max-portfolio or --recent-years.", file=sys.stderr)


if __name__ == "__main__":
    main()
