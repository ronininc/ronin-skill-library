---
name: lead-qualifier
description: Qualify a raw lead list ONE LEAD AT A TIME by verifying each person against their real public web/social presence, then judging whether they actually have the MEANS and authority to do the deal (not just interest) — AND learn from outcomes so targeting gets sharper each time. Outputs an enriched list with a verdict + evidence + verified social links per lead; with feedback, ranks new leads by what actually converts. Use WHENEVER you have a lead list (CSV) and need to keep only HIGH-VALUE, verified leads — "qualify these leads", "check this list", "are these real / do they have money", "verify each lead's socials", "filter out the tire-kickers", "means test the list", "learn from which leads converted", "make it target better", or enriching any lead list with proof. Honest by design: verify identity before trusting anything (reject namesakes), public info only, mark UNVERIFIED rather than guess, never fabricate a link or a verdict; the learner is transparent win-rate-by-signal, not a black box.
---

# Lead Qualifier

Turns a raw lead list into a **verified, means-tested** list. A raw list is cheap and untrustworthy —
anyone can generate one. The value is the **one-at-a-time verification pass**: for each person you reach
their real public presence, confirm it's actually them, and judge whether they have the means/authority
to participate — then attach the evidence. What survives is a list you can hand to a sales team without
wasting their time on people who only *looked* interested.

## When to use
You have a lead list (any CSV) and need only the real, high-value ones: "qualify this list", "double-check
these leads", "do they actually have the money", "verify their socials one by one", "cut the tire-kickers".

## The core idea
**Interest ≠ means.** Broad lists are full of aspirants, employees, content-followers, and namesakes.
This skill separates *showed up on a list* from *can actually do the deal* — using public evidence, per lead.

## Workflow — run it PER LEAD, in order

For **each** lead in the list:

1. **Locate & CONFIRM identity first.** Search `"<name>" "<company>"`, `"<name>" <city> <role>`,
   `"<name>" linkedin`, `"<company>" website`. You are looking for the *specific* person — same name +
   company/city + line of work. **Namesakes are the #1 failure**: a different person with the same name is
   NOT a match. If you cannot confirm it's the same person, verdict = `UNVERIFIED — identity unconfirmed`
   and move on. Do not attach links you couldn't tie to them.
2. **Reach their real surfaces** (highest signal first): their **own website**, **LinkedIn** (person +
   company), then Instagram / X / Facebook / TikTok. Prefer the operator's own site and profiles;
   aggregators/directories are weaker — corroborate, don't trust alone. If you have a
   `business-profile-recon` skill, use its sweep; otherwise WebSearch to locate, WebFetch to read. If a
   fetch is blocked, that field is unverified — never route around it with scripts.
3. **Assess MEANS** against `references/rubric.md`. Look for concrete evidence of capital + authority:
   owns/runs a firm or fund, principal / GP / managing-partner / owner title, documented deals or
   portfolio, accredited-investor signals, a real business footprint. Absence of any means signal (an
   employee, a student, a "guru follower", no firm) = low value even if the identity is real.
4. **Assign a verdict + tier + evidence.** Every verdict cites what you actually saw (with source URLs).
   No evidence → not a high-value verdict.
5. **Record it**, then go to the next lead. Do not batch-guess; the point is per-lead proof.

## Run it
```
# 1) scaffold: normalize the input list + print the per-lead searches, write verdicts.template.json
python3 scripts/qualify.py --worklist --in leads.csv

# 2) (you) work each lead through the workflow above; fill verdicts.json (verified fields only)

# 3) build the qualified output (.csv, plus .xlsx with clickable links if openpyxl is installed)
python3 scripts/qualify.py --build --in leads.csv --verdicts verdicts.json --out "qualified-leads"
```
Input CSV can have any columns — the script auto-detects name / company / email / phone / city / source and
passes the rest through. Output adds: `verdict, tier, means_signals, title_role, website, linkedin,
x_twitter, instagram, facebook, evidence`.

## It learns from outcomes — targeting gets sharper over time
A qualifier that never learns just repeats today's guesses. So the loop closes: **record what actually
happened, and the skill learns which signals predict a good lead — then prioritizes future leads by it.**

1. In a past qualified CSV, add an **`outcome`** column and fill the real result per lead
   (`good` / `converted` / `qualified` / `booked` / `funded` — or `bad` / `dead`).
2. Learn from it → get a `model.json` **and a plain-English targeting playbook**:
   ```
   python3 scripts/qualify.py --learn --history qualified-leads.csv [more-months.csv ...]
   ```
   Example output: `Double down on: source:linkedin, tier:high, means:fund` /
   `Pull back / cut: source:tiktok, email:personal, tier:low`.
3. Feed the model back into future builds so new leads are ranked by **what actually converts**, not just
   the static rubric:
   ```
   python3 scripts/qualify.py --build --in new-leads.csv --verdicts verdicts.json --out qualified \
     --model model.json
   ```
   New leads get a `learned_score` + `priority` and the list sorts by it.

The learner is **transparent** (win-rate per signal, shown as a lift number) — you can read exactly what it
learned and act on it, and it needs no keys or services. It gets better every time you feed it outcomes.

## Verdict tiers (see references/rubric.md for the full rubric)
- **HIGH** — identity verified + at least one strong means signal (runs/owns a fund or firm; GP/principal/
  managing-partner/owner; documented deals/portfolio; accredited signals).
- **MEDIUM** — identity verified + soft means (works in the space, real presence, capital unclear).
- **LOW** — identity verified but no means signals (employee / aspirant / content-only / no firm).
- **UNVERIFIED** — could not confirm identity, or only namesakes found. Not a usable lead.

## Honesty invariants (never break)
- **Verify identity before anything.** A same-name namesake is a miss, not a match.
- **Every link and verdict is sourced or marked.** Unverifiable → blank + UNVERIFIED, never a guess.
- **Public info only.** Don't scrape behind logins, defeat blocks, or compile private personal data.
- **Never fabricate** a handle, a title, a portfolio, or a means signal to make a lead look better.
- **One at a time.** The qualification is per-lead and evidence-based; that discipline is the product.
