#!/usr/bin/env python3
"""Lead Qualifier — verify + means-test a lead list, AND learn from outcomes to target better over time.

Three moves:
  --worklist : normalize the list + print the per-lead recon searches, write verdicts.template.json
  --build    : merge the agent's verdicts.json into a qualified list (CSV [+ XLSX]); if --model is given,
               add a learned priority and sort by it
  --learn    : read past qualified list(s) that have an `outcome` column (good/bad/converted/dead...) and
               learn which SIGNALS predict a good lead -> model.json + a plain-English targeting playbook

The learner is TRANSPARENT on purpose: it's win-rate-by-signal (smoothed Naive-Bayes / log-odds), so you
can SEE what it learned and act on it — not a black box. Standard library only; XLSX if openpyxl present.

Usage:
  qualify.py --worklist --in leads.csv
  qualify.py --build --in leads.csv --verdicts verdicts.json --out qualified-leads [--model model.json]
  qualify.py --learn --history qualified-leads.csv [more.csv ...] [--model-out model.json]
"""
import argparse, csv, json, math, re, sys, os

ALIASES = {
    "name": ["name", "full name", "full_name", "contact", "contact name", "lead", "principal", "person"],
    "company": ["company", "firm", "fund", "business", "organization", "org", "entity", "employer", "sponsor"],
    "email": ["email", "e-mail", "email address"],
    "phone": ["phone", "phone number", "mobile", "cell", "tel"],
    "city": ["city", "location", "market", "metro", "town", "area"],
    "source": ["source", "utm_source", "channel", "utm source", "lead source"],
}
SOCIAL = ["website", "linkedin", "x_twitter", "instagram", "facebook"]
OUT_EXTRA = ["verdict", "tier", "means_signals", "title_role"] + SOCIAL + ["evidence"]
FREEMAIL = {"gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","aol.com","live.com","msn.com"}
GOOD = {"good", "converted", "qualified", "booked", "funded", "closed", "won"}
ROLE_KW = [("gp", r"\bgp\b|general partner"), ("principal", r"principal"), ("owner", r"owner|founder|co-?found"),
           ("partner", r"managing partner|\bpartner\b"), ("clevel", r"\bceo\b|\bcio\b|\bcfo\b|president"),
           ("fundmgr", r"fund manager|portfolio manager|family office")]
MEANS_KW = [("fund", r"\bfund\b|syndicat|raise|capital"), ("deals", r"deal|portfolio|acquisit|track record|aum"),
            ("accredited", r"accredit"), ("realco", r"\bllc\b|\binc\b|firm|company")]


def norm(s): return re.sub(r"\s+", " ", (s or "").strip())
def low(s): return norm(s).lower()


def detect(headers):
    m, lowmap = {}, {low(h): h for h in headers}
    for canon, names in ALIASES.items():
        for nm in names:
            if nm in lowmap: m[canon] = lowmap[nm]; break
    return m


def key_of(lead):
    if lead.get("email"): return low(lead["email"])
    return low(lead.get("name", "")) + "|" + low(lead.get("company", ""))


def load(fn):
    with open(fn, newline="", encoding="utf-8-sig") as fh:
        r = csv.DictReader(fh); return list(r), (r.fieldnames or [])


def canon_lead(row, colmap):
    return {c: norm(row.get(colmap[c], "")) for c in colmap}


# ---------- features we learn on (actionable targeting signals) ----------
def row_features(row, colmap):
    f = []
    if colmap.get("source"):
        v = low(row.get(colmap["source"], ""))
        if v: f.append(f"source:{v}")
    tier = low(row.get("tier", ""))
    if tier: f.append(f"tier:{tier}")
    if colmap.get("email"):
        dom = (re.search(r"@([^@\s]+)$", low(row.get(colmap["email"], ""))) or [None, ""])[1]
        if dom: f.append("email:business" if dom not in FREEMAIL else "email:personal")
    if row.get("linkedin"): f.append("has:linkedin")
    if colmap.get("city"):
        c = low(row.get(colmap["city"], ""))
        if c: f.append(f"city:{c}")
    text = (row.get("title_role", "") + " " + row.get("means_signals", "") + " " + row.get("verdict", "")).lower()
    for kw, rx in ROLE_KW:
        if re.search(rx, text): f.append(f"role:{kw}")
    for kw, rx in MEANS_KW:
        if re.search(rx, text): f.append(f"means:{kw}")
    return f


def is_good(o): return low(o) in GOOD


# ---------- worklist ----------
def worklist(rows, colmap, out_template):
    if not any(k in colmap for k in ("name", "company", "email")):
        sys.exit("No name/company/email column. Headers: " + ", ".join(rows[0].keys() if rows else []))
    template = {}
    print(f"# {len(rows)} leads to qualify — run each through SKILL.md (identity FIRST).\n")
    for row in rows:
        lead = canon_lead(row, colmap)
        who = " / ".join(x for x in [lead.get("name",""), lead.get("company",""), lead.get("city","")] if x) or lead.get("email","?")
        qs = []
        if lead.get("name") and lead.get("company"): qs.append(f'"{lead["name"]}" "{lead["company"]}"')
        if lead.get("name") and lead.get("city"): qs.append(f'"{lead["name"]}" {lead["city"]} investor')
        if lead.get("name"): qs.append(f'"{lead["name"]}" linkedin')
        if lead.get("company"): qs.append(f'"{lead["company"]}" website')
        print(f"## {who}\n   searches: " + "  ·  ".join(qs))
        template[key_of(lead)] = {"identity_confirmed": False, "title_role": "", "website": "", "linkedin": "",
            "x_twitter": "", "instagram": "", "facebook": "", "means_signals": "",
            "verdict": "UNVERIFIED — identity unconfirmed", "tier": "UNVERIFIED", "evidence": ""}
    json.dump(template, open(out_template, "w", encoding="utf-8"), indent=1)
    print(f"\n-> wrote {out_template} ({len(template)} leads). Fill verified fields only, then --build.")


# ---------- learn ----------
def train(histories):
    rows_all = []
    for fn in histories:
        rows, headers = load(fn)
        cm = detect(headers)
        for row in rows:
            if not is_good(row.get("outcome", "")) and low(row.get("outcome", "")) == "":
                continue  # unlabeled — skip
            if low(row.get("outcome", "")) == "":
                continue
            rows_all.append((row, cm))
    labeled = [(r, cm) for (r, cm) in rows_all if low(r.get("outcome", "")) != ""]
    n = len(labeled)
    if not n: sys.exit("No labeled rows found. Add an `outcome` column (good/bad/converted/dead...) first.")
    goods = sum(1 for r, _ in labeled if is_good(r.get("outcome", "")))
    base = goods / n
    stat = {}
    for row, cm in labeled:
        g = 1 if is_good(row.get("outcome", "")) else 0
        for ft in set(row_features(row, cm)):
            s = stat.setdefault(ft, {"good": 0, "total": 0}); s["good"] += g; s["total"] += 1
    A = 1.0
    feats = {}
    for ft, s in stat.items():
        rate = (s["good"] + A * base) / (s["total"] + A)
        lift = math.log(rate / (1 - rate)) - math.log(base / (1 - base)) if 0 < base < 1 else 0.0
        feats[ft] = {"good": s["good"], "total": s["total"], "rate": round(rate, 3), "lift": round(lift, 3)}
    return {"base": round(base, 3), "n": n, "features": feats}


def learn(histories, model_out):
    model = train(histories)
    json.dump(model, open(model_out, "w"), indent=1)
    ranked = sorted(model["features"].items(), key=lambda kv: kv[1]["lift"], reverse=True)
    print(f"Learned from {model['n']} labeled leads (base good-rate {round(model['base']*100)}%).\n")
    print("SIGNALS (what predicts a GOOD lead):")
    for ft, w in ranked:
        if w["total"] < 2: continue
        a = "UP  " if w["lift"] > 0 else ("DOWN" if w["lift"] < 0 else "flat")
        print(f"  {a}  {ft:<20} {w['good']}/{w['total']} good ({round(w['rate']*100):>3}%)  lift {w['lift']:+.2f}")
    up = [ft for ft, w in ranked if w["lift"] >= 0.5 and w["total"] >= 2][:4]
    dn = [ft for ft, w in ranked[::-1] if w["lift"] <= -0.5 and w["total"] >= 2][:4]
    print("\nTARGETING PLAYBOOK:")
    if up: print("  Double down on: " + ", ".join(up))
    if dn: print("  Pull back / cut: " + ", ".join(dn))
    print(f"\n-> wrote {model_out}. Pass it to --build to prioritize new leads by what actually converts.")


def learned_score(feats, model):
    if not model or not model.get("n"):
        return None
    base = model["base"]
    z = math.log(base / (1 - base)) if 0 < base < 1 else 0.0
    for ft in feats:
        w = model["features"].get(ft)
        if w and w["total"] >= 2: z += w["lift"]
    return round(100 / (1 + math.exp(-z)))


# ---------- build ----------
TIER_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNVERIFIED": 3}


def build(rows, colmap, verdicts, out_base, model):
    passthrough = list(rows[0].keys()) if rows else []
    extra = [c for c in OUT_EXTRA if c not in passthrough]
    learn_cols = ["learned_score", "priority"] if model else []
    cols = passthrough + extra + learn_cols
    out_rows, tier_count = [], {}
    for row in rows:
        lead = canon_lead(row, colmap)
        v = verdicts.get(key_of(lead), {})
        merged = dict(row)
        for c in OUT_EXTRA: merged[c] = v.get(c, "")
        tier = (merged.get("tier") or "UNVERIFIED").upper()
        tier_count[tier] = tier_count.get(tier, 0) + 1
        if model:
            ls = learned_score(row_features(merged, colmap), model)
            merged["learned_score"] = "" if ls is None else ls
            merged["priority"] = ls if ls is not None else (100 - TIER_RANK.get(tier, 3) * 25)
        out_rows.append(merged)
    if model:
        out_rows.sort(key=lambda r: r.get("priority") or 0, reverse=True)
    else:
        out_rows.sort(key=lambda r: TIER_RANK.get((r.get("tier") or "UNVERIFIED").upper(), 3))

    with open(out_base + ".csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(out_rows)
    made = write_xlsx(out_base + ".xlsx", cols, out_rows)
    summary = " | ".join(f"{k} {tier_count[k]}" for k in ["HIGH","MEDIUM","LOW","UNVERIFIED"] if k in tier_count)
    print(f"WROTE {out_base}.csv" + (f" + {out_base}.xlsx" if made else " (pip install openpyxl for .xlsx)")
          + f"  |  {len(out_rows)} leads  |  {summary}" + (f"  |  sorted by learned priority" if model else ""))


def write_xlsx(path, cols, rows):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return False
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Qualified Leads"
    ws.append([c.replace("_", " ").title() for c in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="1F3B4D")
    tier_fill = {"HIGH": "1E8F4E", "MEDIUM": "B8860B", "LOW": "6B7280", "UNVERIFIED": "9A3B3B"}
    link_font = Font(color="1155CC", underline="single")
    for r in rows:
        ws.append([r.get(c, "") for c in cols]); rn = ws.max_row
        for c in SOCIAL + ["website"]:
            if c in cols and str(r.get(c, "")).startswith("http"):
                cell = ws.cell(row=rn, column=cols.index(c) + 1); cell.hyperlink = r[c]; cell.font = link_font
        if "tier" in cols:
            t = (r.get("tier") or "").upper()
            if t in tier_fill:
                ws.cell(row=rn, column=cols.index("tier") + 1).fill = PatternFill("solid", fgColor=tier_fill[t])
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 34 if c in ("evidence", "means_signals") else 18
    ws.freeze_panes = "A2"; wb.save(path); return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--worklist", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--learn", action="store_true")
    ap.add_argument("--verdicts", default="verdicts.json")
    ap.add_argument("--out", default="qualified-leads")
    ap.add_argument("--out-template", default="verdicts.template.json")
    ap.add_argument("--model", default=None, help="model.json to prioritize --build by learned score")
    ap.add_argument("--model-out", default="model.json")
    ap.add_argument("--history", nargs="+", help="past qualified CSV(s) with an `outcome` column, for --learn")
    a = ap.parse_args()
    if a.learn:
        if not a.history: sys.exit("--learn needs --history <qualified.csv ...>")
        return learn(a.history, a.model_out)
    if not a.inp: sys.exit("--in is required")
    rows, headers = load(a.inp)
    if not rows: sys.exit("No rows in " + a.inp)
    colmap = detect(headers)
    if a.worklist:
        worklist(rows, colmap, a.out_template)
    elif a.build:
        model = json.load(open(a.model)) if a.model and os.path.exists(a.model) else None
        build(rows, colmap, json.load(open(a.verdicts, encoding="utf-8")), a.out, model)
    else:
        sys.exit("pass --worklist, --build, or --learn")


if __name__ == "__main__":
    main()
