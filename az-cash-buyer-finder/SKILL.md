---
name: az-cash-buyer-finder
description: Build ranked, HONEST Arizona (Maricopa / Phoenix metro) real-estate investor lists from PUBLIC records — four distinct populations, do not conflate them. (1) CASH BUYERS / dispo — who you SELL an assigned deal to: LLC-owned SFRs ranked by recent acquisitions (find_buyers.py). (2) JV OPERATOR partners — who you PARTNER with to co-wholesale/split a deal: local, human-scale, active operators from the same Assessor data, scoring INVERTED (find_jv_partners.py). (3) CAPITAL / PRIVATE-MONEY / JV-EQUITY funders — who FUNDS your deal for an equity split: reachable AZ private/hard-money lenders from public lender directories, flagged by their stated "will consider equity JV" (free path), or transaction-verified Deed-of-Trust beneficiaries (paid/gated). (4) EXPANDING JV / SYNDICATION investors tracked by their FILINGS — SEC Reg D Form D issuers actively raising capital to acquire, with NAMED principals + offering size + capital-still-to-deploy (find_expanding_jv_investors.py). Use WHENEVER the task is a buyer / cash-buyer / dispo list, a JV / joint-venture / partner / private-money / funder / capital-partner list, "who's expanding / raising / buying in AZ", tax-motivated / 1031 / Opportunity-Zone buyers, or enriching any of these. Honest by design: Maricopa-only for Assessor, "cash" is an unverified PROXY, phones are NEVER fabricated (skip-trace), and the private-lender/1031 transaction-verified pull needs a paid provider or county bulk-data request (the Recorder is WAF-blocked).
---

# AZ Active Cash-Buyer Finder

Turns the public **Maricopa County Assessor** parcel database into a ranked list of the investors most
actively buying single-family homes right now — the people a wholesaler sells deals to.

## When to use
A buyer/disposition list is wanted: "give me cash buyers", "who's buying in Phoenix", "dispo list",
"active flippers/landlords", "who do I sell this deal to", or to grow/enrich an existing buyer list.
(For motivated SELLERS to acquire from, use the leadengine residential connector, not this.)

## How it works
Active investors show up in public data as **LLCs that own many single-family homes and keep buying
recently.** Portfolio size + recent acquisition = activity = "the ones with the most luck."
- Source: `gis.mcassessor.maricopa.gov/.../MaricopaDynamicQueryService/MapServer/3/query` (free, public).
- Filter: `OWNER_NAME LIKE '%LLC%' AND PUC='0131'` (PUC 0131 = single-family residential) `AND` a recent
  `SALE_DATE` (last N years). Server-side group-by-count ranks owners; each row carries the mailing address.

## Run it
```
python3 scripts/find_buyers.py --count 200 --recent-years 3
# options: --puc 0131 (SFR; try 0141 for condos/townhomes) · --out /path/to/list.csv
```
Output CSV columns: `rank, entity, recent_buys, total_sfr_portfolio, mailing_address, mail_city,
mail_state, mail_zip, locale, tier, phone(blank)`. Rank by `recent_buys`; filter `locale=AZ-local` +
`tier` not institutional for the local wholesale sweet spot.

## Honesty invariants (never break)
- **"Cash" is a proxy**, not verified — Assessor has no mortgage field. Call them "active investor entities".
- **No fabricated phones.** The `phone` column ships blank; fill it only from a real skip-trace/lookup.
- **Mailing address is the channel** (direct mail). It is a real, public reachability path.
- **Maricopa only.** Say so; other AZ counties need their own assessor source.
- **Single-page fetch** for the ranking (grouped-stats offset paging double-counts tied groups); the
  script enforces `recent_buys <= total_sfr_portfolio`.

## Enrichment ladder — getting phones (proven, honest)
The Assessor gives the LLC + mailing address, not a phone. To reach a human:
1. **eCorp is NOT a phone source and is retired.** The AZ Corporation Commission's legacy `eCorp` was
   replaced Jan 2026 by the **Arizona Business Center** (`arizonabusinesscenter.azcc.gov`). Its records
   list the **statutory agent + principals (names + addresses)** — NOT phone numbers — and its API is
   **CAPTCHA-gated**, so do not bulk-scrape it. It is a manual "who's behind the LLC" unmask, not a phone feed.
2. **Skip-trace (scalable, paid)** — feed the entity/principal + mailing address to BatchSkipTracing / TLO /
   IDI / PropStream-BatchLeads. This is how real phones are obtained (~$0.10–0.25/record).
3. **Best-effort web lookup (free, low hit-rate)** — LLC shell names rarely surface a phone; only the
   larger operators have a site/Google Business. Do not expect coverage across a 200-list.

## JV / partner prospects — NOT the same as cash buyers
A **cash buyer** is who you SELL an assigned deal to (dispo). A **JV prospect** is who you PARTNER with
on a deal. Do not conflate them. There are two distinct JV populations, each with its own source:

### 1) Operator / deal partners (co-wholesale, split the fee) — buildable now, free
Active LOCAL investor-operators you partner with to source/move deals. Same Maricopa Assessor source,
INVERTED scoring: AZ-local only, institutional funds excluded, human-scale portfolio (2–40 SFR), ranked
by recent activity + velocity (recent buys ÷ portfolio = who is transacting now, partner-hungry).
```
python3 scripts/find_jv_partners.py --count 200 --recent-years 3 --min-portfolio 2 --max-portfolio 40
```
Honesty ceiling: this CANNOT verify "wholesaler" — a pure wholesaler assigns before closing and never
takes title, so they may not appear as an owner at all. It surfaces active local operators = realistic
deal partners. The true buy-AND-sell velocity signal lives in the County Recorder grantor/grantee index.

### 2) Capital / private-money partners (fund your deal for an equity split) — two honest paths
Private lenders do NOT own the houses; they are the **beneficiary on recorded Deeds of Trust**. There is
NO free, scriptable feed for this in Maricopa:
- **Path A — reachable lenders (now, free):** research public lender directories (privatelenderlink.com
  Phoenix/Maricopa pages, lendersa, company sites). Their profiles expose a structured
  **"Will Consider Equity Joint Venture: yes/no"** field — filter on the lenders' OWN stated answer to
  find true equity-JV funders (e.g. Kayak Capital, Hilton Financial, Metro Private Lending are AZ-local
  JV-yes). Directory-sourced = reachable today, not "verified active in Maricopa this quarter." ~20 real
  funders, not 200. Never fabricate a phone/site — leave blank + "verify" if not seen on a page.
- **Path B — transaction-verified (paid/gated):** the ideal list = repeat Deed-of-Trust beneficiaries
  (banks/credit unions/MERS excluded) ranked by lending activity. The Maricopa Recorder is WAF-blocked to
  scripts (403) with no free DOT API, so this needs a data provider (PropStream / DataTree / BatchLeads /
  ListSource "private lender" pull) or a county bulk-data request (maricopa.gov/509/Data-Requests). Wire
  the miner behind that access; do not scrape the CAPTCHA/WAF gov site.

### 3) Expanding JV investors, tracked by their filings — buildable now, free (STRONGEST forward signal)
Known JV / syndication operators who are RAISING CAPITAL to acquire show up in **SEC Reg D Form D**
filings. This is a FORWARD signal (money being raised now), unlike the Assessor (deals already closed).
```
python3 scripts/find_expanding_jv_investors.py --start 2025-01-01 --max-issuers 150
# options: --terms "real estate,multifamily,apartment"  --all-az (full-recall industry scan, slower)
```
Source: EDGAR full-text search (`efts.sec.gov`) + each filing's structured `primary_doc.xml`. Use the
WORKING state filter **`locationCodes=AZ`** (plural; singular `locationCode` is silently ignored). Output:
issuer, city, industry, filing type/date, **total offering, amount sold, amount REMAINING** (offering -
sold = capital still to deploy — the rank key), min investment, and **named principals** (Exec Officer /
Director / Promoter) + the filing URL. "Still raising" = amount_sold < offering = actively expanding.
Honesty: no phones in Form D (reach via entity address / named principal / the filing); ~5% cross-industry
noise is left visible in the `industry` column for the user to filter, not silently dropped.

### 4) Tax-motivated (FORCED) buyers — the motivated-seller logic, inverted
The mirror of a motivated seller is a buyer under a DEADLINE or tax penalty. Highest-intent types:
- **1031 exchangers** — just SOLD; IRS clock forces reinvestment (45 days to identify, 180 to close) or
  they owe capital-gains tax. Signal = a RECENT SELLER (grantor on a just-recorded deed). That lives in
  the County Recorder (gated/paid — same wall as private lenders, path B above), so there is NO free list.
  Reach them via 1031 Qualified Intermediaries / DST sponsors (they aggregate exchangers) and by marketing
  "1031-ready replacement property."
- **Year-end depreciation / cost-seg buyers** — high-income buyers acquiring before Dec 31 for bonus
  depreciation to offset ordinary income (esp. real-estate professionals & short-term-rental "loophole").
- **Opportunity Zone investors** — defer capital gains via OZ property/funds. THESE ARE ALREADY IN THE
  FORM D LIST (e.g. "Caliber Tax Advantaged Opportunity Zone Fund") — filter `industry`/issuer name for
  "Opportunity Zone" to pull tax-driven buyers directly.
Targeting rule: pitch these buyers on the TAX BENEFIT of the specific asset (depreciation schedule, 1031
fit, OZ eligibility), not just the spread — the deadline/penalty is the motivation lever.

### 5) JV prospect SPREADSHEET with VERIFIED social links — drop-in (`enrich_jv_socials.py`)
Turn any JV prospect CSV (usually the Form D syndicators) into an .xlsx with a **clickable, VERIFIED social
link per prospect** (website · LinkedIn · X · Instagram · Facebook · lead-principal LinkedIn) alongside all
the filing data. The script is the deterministic scaffold + assembler; the VERIFICATION is an agent step
that **uses the `anthropic-skills:business-profile-recon` ("owner.com") skill** — reach each sponsor's OWN
site + LinkedIn, then X/IG/FB, and confirm the handle belongs to THIS entity by matching the SEC filing's
named principals + AZ + real-estate context. Never fabricate a handle.
```
# 1) scaffold: group issuers by sponsor brand + print the recon searches, write socials.template.json
python3 scripts/enrich_jv_socials.py --worklist --in "AZ Expanding JV Investors — SEC Form D (Arizona).csv"
# 2) agent runs business-profile-recon per sponsor, fills socials.json (verified links only)
# 3) build the spreadsheet (xlsx w/ hyperlinks + csv mirror)
python3 scripts/enrich_jv_socials.py --build --in "<same csv>" --socials socials.json --out "JV + Socials"
```
Honesty invariants baked in: the `verification` column carries **VERIFIED / PARTIAL / "UNVERIFIED - run
recon" / "UNVERIFIED - not found"**; a link appears ONLY when a source confirmed it (namesake collisions —
e.g. two "Cline"s, two "Caliber" IG accounts — stay blank + UNVERIFIED). Grouping by SPONSOR BRAND means
one recon covers all of a sponsor's funds (14 Caliber funds → one caliberco.com/LinkedIn lookup). For 100+
issuers, fan the recon out with parallel agents (one per brand-batch), each returning verified-links-only.

## Extension points
- Add counties: point at Pima/Pinal assessor GIS services (schema differs).
- Widen property type via `--puc` (condos/townhomes/2–4 unit) for buyers of those.
- Dedupe institutional multi-LLC operators by shared mailing address before counting "distinct buyers".
- Add a real skip-trace step behind a paid-provider flag to populate the `phone` column.
