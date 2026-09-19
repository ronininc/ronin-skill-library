#!/usr/bin/env python3
"""Clone a client-owned lead CRM into a client's OWN Notion workspace via the Notion API.

Two shapes from one script:
  --shape marketplace  (default) : two-sided case-matching marketplace (e.g. Case Plug) —
                                   Consumer Leads -> Match -> Attorney Partners + Billing + Marketing ROI.
  --shape firm                   : single-firm intake CRM (Leads + Marketing + Referral + Signed Cases).

Scope: leads / intake / matching / marketing ROI / billing. NO PHI (injury = severity buckets, never
medical records). Compliance fields are baked into the schema (Sourcing, Consent, Payment Model, Fee
agreement, Already-Represented) so the system nudges toward the defensible lane and FLAGS the rest.

STATUS: authored against the Notion API (2022-06-28). NOT yet run against a live workspace — verify on a
test token first (build into a throwaway page, confirm, then the client's page). Relations/rollups are a
second PATCH pass because a relation's target database must exist first.

Usage:
  NOTION_TOKEN=secret_xxx  python3 setup_notion_crm.py --parent <PARENT_PAGE_ID> [--shape marketplace|firm]
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

API, VER = "https://api.notion.com/v1", "2022-06-28"


def call(method, path, body=None):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("Set NOTION_TOKEN (a Notion internal-integration secret). Nothing was created.")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Notion-Version": VER, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Notion API {e.code} on {method} {path}: {e.read().decode()[:400]}")
    finally:
        time.sleep(0.4)  # stay under ~3 req/s


def sel(*o): return {"select": {"options": [{"name": n} for n in o]}}
def ms(*o):  return {"multi_select": {"options": [{"name": n} for n in o]}}
def title(): return {"title": {}}
def rt():    return {"rich_text": {}}
def money(): return {"number": {"format": "dollar"}}
def rel(t):  return {"relation": {"database_id": t, "single_property": {}}}
def rollup(r, p, fn): return {"rollup": {"relation_property_name": r, "rollup_property_name": p, "function": fn}}
def db(parent, name, props):
    d = call("POST", "/databases", {"parent": {"type": "page_id", "page_id": parent},
             "title": [{"type": "text", "text": {"content": name}}], "properties": props})
    print(f"  created DB: {name} -> {d['id']}"); return d["id"]
def add(dbid, props): call("PATCH", f"/databases/{dbid}", {"properties": props})

CASE_TYPES = ("Auto", "Truck", "Motorcycle", "Slip-Fall", "Premises", "Dog Bite", "Med-Mal", "Wrongful Death", "Other")


def marketplace(p):
    channels = db(p, "Marketing Channels", {"Channel": title(),
        "Type": sel("Google LSA", "Google PPC", "SEO", "Meta", "TikTok", "TV", "Radio", "Referral"),
        "Monthly Spend": money()})
    partners = db(p, "Attorney Partners", {"Firm / Attorney": title(), "Contact": rt(),
        "States Covered": ms("AZ", "CA", "TX", "FL", "GA", "NY"), "Case Types Accepted": ms(*CASE_TYPES),
        "Capacity": sel("Accepting", "Paused", "Full"),
        "Payment Model": sel("Flat-per-lead", "Per-signed", "%-recovery"),  # default flat in UI
        "Per-lead Price": money(), "Fee Agreement On File": {"checkbox": {}}})
    staff = db(p, "Staff / Intake Team", {"Name": title(), "Role": sel("Intake", "Matcher", "Manager", "Marketing")})
    leads = db(p, "Consumer Leads", {"Name": title(), "Phone": {"phone_number": {}}, "Email": {"email": {}},
        "Case Type": sel(*CASE_TYPES), "Incident Date": {"date": {}}, "State": rt(),
        "Injury Severity": sel("ER", "Hospital", "Surgery", "Ongoing Tx", "Minor"),
        "Liability": sel("Clear", "Disputed", "Unknown"),
        "Insurance": sel("Yes", "Uninsured", "UM-UIM", "Unknown"),
        "Already Represented": {"checkbox": {}},          # auto-disqualify
        "Consent / TCPA Opt-in": {"checkbox": {}},        # compliance
        "Sourcing": sel("Inbound", "Purchased", "Unknown"),  # compliance flag
        "Stage": {"status": {}}, "First Contact": {"date": {}}, "Notes": rt()})
    matches = db(p, "Matches", {"Match": title(), "Match Date": {"date": {}},
        "Status": sel("Offered", "Accepted", "Rejected", "Signed", "Billable", "Paid"),
        "Price": money(), "Delivered": {"checkbox": {}}})
    billing = db(p, "Billing / Invoices", {"Invoice": title(), "Period": rt(), "Amount": money(),
        "Status": sel("Draft", "Sent", "Paid")})
    tasks = db(p, "Tasks / Follow-ups", {"Task": title(), "Due": {"date": {}},
        "Status": sel("To Do", "Doing", "Done"), "Type": sel("Callback", "Match", "Follow-up")})

    # relations
    add(leads, {"Source": rel(channels), "Assigned To": rel(staff)})
    add(matches, {"Consumer Lead": rel(leads), "Attorney Partner": rel(partners)})
    add(billing, {"Attorney Partner": rel(partners), "Billable Matches": rel(matches)})
    add(tasks, {"Lead": rel(leads), "Match": rel(matches)})
    # back-relations + rollups for ROI / scoreboards
    add(channels, {"Leads": rel(leads)}); add(channels, {"# Leads": rollup("Leads", "Name", "count")})
    add(partners, {"Matches": rel(matches)}); add(partners, {"# Matches": rollup("Matches", "Match", "count")})
    add(staff, {"Leads Handled": rel(leads)}); add(staff, {"# Leads": rollup("Leads Handled", "Name", "count")})
    print("\nMARKETPLACE done. In Notion: set Leads 'Stage' groups (New->Attempted->Contacted->Qualified->"
          "Matched->Delivered->Rejected), default Partner 'Payment Model'=Flat-per-lead, add speed-to-lead "
          "formula, and build the Matching-queue + Marketing-ROI + COMPLIANCE views (Sourcing!=Inbound / "
          "Consent missing / Payment Model=%-recovery).")


def firm(p):
    channels = db(p, "Marketing Channels", {"Channel": title(),
        "Type": sel("Google LSA", "Google PPC", "SEO", "Meta", "Referral"), "Monthly Spend": money()})
    referral = db(p, "Referral Network", {"Name": title(),
        "Type": sel("Chiropractor", "PT", "Ortho", "Body Shop", "Co-Counsel", "Other"), "Contact": rt()})
    leads = db(p, "Leads", {"Name": title(), "Phone": {"phone_number": {}}, "Email": {"email": {}},
        "Case Type": sel(*CASE_TYPES), "State": rt(), "Injury Severity": sel("ER", "Hospital", "Surgery", "Ongoing Tx", "Minor"),
        "Already Represented": {"checkbox": {}}, "Stage": {"status": {}}, "Est Case Value": money(), "Notes": rt()})
    add(leads, {"Source": rel(channels), "Referred By": rel(referral)})
    add(channels, {"Leads": rel(leads)}); add(channels, {"# Leads": rollup("Leads", "Name", "count")})
    print("\nFIRM done. Finish the pipeline status + SOL/speed formulas + views in Notion.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--parent", required=True)
    ap.add_argument("--shape", choices=["marketplace", "firm"], default="marketplace"); a = ap.parse_args()
    print(f"Cloning {a.shape} CRM into parent page {a.parent}")
    (marketplace if a.shape == "marketplace" else firm)(a.parent)


if __name__ == "__main__":
    main()
