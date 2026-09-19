# Install — lead-qualifier skill

A portable Claude Code skill. It qualifies a raw lead list one lead at a time: verifies each person's
real identity + socials via public web recon, judges whether they actually have the MEANS to do the deal
(not just interest), and outputs an enriched list with a verdict + evidence per lead.

## Install (pick one)
- **User-wide:** unzip so the folder lives at `~/.claude/skills/lead-qualifier/`
- **One project:** unzip to `<your-project>/.claude/skills/lead-qualifier/`

Then in Claude Code just say: *"qualify this lead list"* and hand it a CSV — Claude will load the skill.

## Use (3 steps)
```
# 1) scaffold the per-lead worklist + an empty verdicts file
python3 scripts/qualify.py --worklist --in leads.csv

# 2) Claude works each lead through SKILL.md (identity first, then means) and fills verdicts.json

# 3) build the qualified output — CSV always; XLSX with clickable links if openpyxl is installed
python3 scripts/qualify.py --build --in leads.csv --verdicts verdicts.json --out qualified-leads
```
Input CSV can have any headers — name / company / email / phone / city / source are auto-detected; other
columns pass through. Output is sorted HIGH → MEDIUM → LOW → UNVERIFIED.

## It learns (targeting improves with feedback)
```
# add an `outcome` column (good/converted/bad/dead...) to a past qualified CSV, then:
python3 scripts/qualify.py --learn --history qualified-leads.csv   # -> model.json + a targeting playbook
# then prioritize new leads by what actually converts:
python3 scripts/qualify.py --build --in new-leads.csv --verdicts verdicts.json --out qualified --model model.json
```
The learner is transparent (win-rate per signal) — it prints exactly what it learned ("double down on
LinkedIn + fund language, cut TikTok + personal email") and re-ranks new leads accordingly. No keys, no services.

## What makes a lead HIGH vs LOW
See `references/rubric.md`. Short version: **identity must verify first** (a same-name namesake is a miss),
then it's HIGH only with a real **means** signal — owns/runs a fund or firm, GP/principal/owner title,
documented deals, accredited/capital signals. A verified person with no means (employee, aspirant, or a
real business in the wrong field) is LOW, not HIGH. Every verdict cites its evidence; unverifiable = blank,
never guessed.

Requires: `python3` (standard library only). Optional: `pip install openpyxl` for the .xlsx output.
Recon uses Claude's web search/fetch; no API keys needed.
