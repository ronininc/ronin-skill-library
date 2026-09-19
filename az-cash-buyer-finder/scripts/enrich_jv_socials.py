#!/usr/bin/env python3
"""Turn a JV prospect CSV into a SPREADSHEET with a VERIFIED social link per prospect (+ all the other
info). This is the deterministic scaffold + assembler; the VERIFICATION itself is done by the agent using
the business-profile-recon skill ("the owner.com skill") and recorded in a socials JSON — never fabricated.

FLOW (drop-in):
  1) --worklist  : read the JV CSV, group issuers by SPONSOR BRAND, and print the exact recon searches to
                   run per sponsor. Also writes socials.template.json (one empty record per brand).
  2) (agent)     : run business-profile-recon on each sponsor — reach its OWN site + LinkedIn, then X / IG /
                   FB — and fill socials.json. Fill a link ONLY when verified (name + AZ + real-estate match
                   against the SEC filing). Leave blank + set status otherwise. NEVER invent a handle.
  3) --build     : join the JV CSV + socials.json into an .xlsx (clickable hyperlinks) and a .csv mirror,
                   one row per fund with all Form D info + the sponsor's verified socials + a status column.

HONESTY INVARIANTS (do not remove):
  * A social link is present ONLY if a human-verifiable source confirmed it belongs to THIS entity. The
    `verification` column carries VERIFIED / PARTIAL / "UNVERIFIED - run recon" / "UNVERIFIED - not found".
    Namesake collisions (e.g. two "Cline"s, two "Caliber"s) => leave blank + UNVERIFIED, per recon skill.
  * Reconnaissance, not surveillance: public BUSINESS profiles of the entity and its filing-named
    principals only. No private personal data, no scraping behind logins.
  * No phones are invented; the SEC filing URL is the identity anchor for every row.

Usage:
  enrich_jv_socials.py --worklist --in "AZ Expanding JV Investors — SEC Form D (Arizona).csv"
  enrich_jv_socials.py --build    --in "<same csv>" --socials socials.json --out "AZ JV Prospects + Socials"
"""
import argparse, csv, html, json, re, collections, sys

GENERIC = {"FUND","FUNDCO","LLC","LP","INC","PARTNERS","CAPITAL","GROWTH","INCOME","REAL","ESTATE","OWNER",
           "CO","INVESTOR","INVESTMENTS","HOLDINGS","EQUITY","OPPORTUNITY","ZONE","QOF","DST","PREFERRED",
           "AND","THE","OF","II","III","IV","I","V","VI","GROUP","SP","TSMC","LTO","AHP","FSO","REIT"}
SOCIAL_COLS = ["website", "linkedin", "x_twitter", "instagram", "facebook", "lead_principal_linkedin"]


def brand(name):
    for t in re.split(r"[^A-Za-z0-9]+", html.unescape(name).upper()):
        if t and t not in GENERIC and len(t) > 2 and not t.isdigit():
            return t.title()
    return html.unescape(name).split()[0].title() if name.strip() else "Unknown"


def clean_prin(s):
    return [re.sub(r"\s*\([^)]*\)", "", p).strip() for p in s.split(";")
            if p.strip() and " LLC" not in p and not p.strip().lower().startswith(("n/a", "--"))]


def load(fn):
    return list(csv.DictReader(open(fn, encoding="utf-8")))


def money(s):
    try: return int(float(s))
    except (TypeError, ValueError): return None


def worklist(rows, out_json):
    agg = collections.defaultdict(lambda: {"funds": 0, "rem": 0, "cities": set(), "prin": set(), "issuers": []})
    for r in rows:
        b = brand(r["issuer"]); a = agg[b]
        a["funds"] += 1; a["rem"] += money(r.get("amount_remaining")) or 0
        a["cities"].add(r.get("city", "").title()); a["issuers"].append(html.unescape(r["issuer"]))
        for p in clean_prin(r.get("principals", "")): a["prin"].add(p)
    order = sorted(agg.items(), key=lambda kv: kv[1]["rem"], reverse=True)
    template = {}
    print(f"# {len(order)} sponsor brands to verify (run business-profile-recon on each)\n")
    for b, a in order:
        city = sorted(c for c in a["cities"] if c)[:1]
        citys = city[0] if city else "AZ"
        print(f"## {b}  ({a['funds']} fund(s), ~${a['rem']:,} to deploy, {citys})")
        print(f"   searches: \"{b}\" {citys} real estate fund website  ·  \"{b}\" LinkedIn  ·  \"{b}\" instagram")
        if a["prin"]:
            print(f"   principals to match (from SEC filing): {', '.join(sorted(a['prin'])[:5])}")
        template[b] = {"website": "", "linkedin": "", "x_twitter": "", "instagram": "", "facebook": "",
                       "lead_principal_linkedin": "", "verification": "UNVERIFIED - run recon", "sources": ""}
    json.dump(template, open(out_json, "w"), indent=2)
    print(f"\n-> wrote {out_json} ({len(template)} brands). Fill verified links, then run --build.")


def build(rows, socials, out_base):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    S = {k: v for k, v in socials.items()}
    cols = ["issuer", "sponsor_brand", "city", "industry", "filing_date", "offering_amount",
            "amount_remaining", "pct_sold", "principals"] + SOCIAL_COLS + ["verification", "recon_sources",
            "sec_filing"]
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "JV Prospects"
    head_font = Font(bold=True, color="FFFFFF"); head_fill = PatternFill("solid", fgColor="1F3B4D")
    link_font = Font(color="1155CC", underline="single")
    ws.append([c.replace("_", " ").title() for c in cols])
    for cell in ws[1]:
        cell.font = head_font; cell.fill = head_fill; cell.alignment = Alignment(vertical="center")
    csv_rows = []
    for r in rows:
        b = brand(r["issuer"]); s = S.get(b, {})
        rem = money(r.get("amount_remaining"))
        row = {"issuer": html.unescape(r["issuer"]), "sponsor_brand": b, "city": r.get("city", "").title(),
               "industry": r.get("industry", ""), "filing_date": r.get("filing_date", ""),
               "offering_amount": r.get("offering_amount", ""), "amount_remaining": rem if rem else "",
               "pct_sold": r.get("pct_sold", ""), "principals": html.unescape(r.get("principals", "")),
               "verification": s.get("verification", "UNVERIFIED - run recon"),
               "recon_sources": s.get("sources", ""), "sec_filing": r.get("filing_url", "")}
        for k in SOCIAL_COLS:
            row[k] = s.get(k, "")
        csv_rows.append(row)
        ws.append([row[c] for c in cols])
        rn = ws.max_row
        for k in SOCIAL_COLS + ["sec_filing"]:
            v = row[k]
            if v and str(v).startswith("http"):
                c = ws.cell(row=rn, column=cols.index(k) + 1)
                c.hyperlink = v; c.font = link_font
    widths = {"issuer": 40, "sponsor_brand": 14, "principals": 46, "website": 26, "linkedin": 30,
              "x_twitter": 22, "instagram": 26, "facebook": 26, "lead_principal_linkedin": 30,
              "verification": 22, "recon_sources": 30, "sec_filing": 20, "industry": 18}
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = widths.get(c, 15)
    ws.freeze_panes = "A2"
    xlsx = out_base + ".xlsx"; wb.save(xlsx)
    with open(out_base + ".csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(csv_rows)
    ver = sum(1 for r in csv_rows if r["verification"].startswith("VERIFIED"))
    print(f"WROTE {xlsx}  ({len(csv_rows)} rows, {ver} rows with a VERIFIED social; rest marked for recon)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--worklist", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--socials", default="socials.json")
    ap.add_argument("--out", default="AZ JV Prospects + Verified Socials")
    a = ap.parse_args()
    rows = load(a.inp)
    if a.worklist:
        worklist(rows, a.socials)
    elif a.build:
        build(rows, json.load(open(a.socials)), a.out)
    else:
        sys.exit("pass --worklist or --build")


if __name__ == "__main__":
    main()
