# Lead Workbook — the deliverable (a spreadsheet + attached site files)

The deliverable is a **spreadsheet**, not a web dashboard. Jordi (the salesperson)
works from a normal sheet and, before walking into a shop, clicks that shop's
website link and the **prebuilt template opens rendered in his browser**. Nothing
fancy, nothing to explain. A working example builder is `assets/workbook-builder.py`.

**Do NOT build an HTML "onboarding dashboard."** That was wrong — the operator hates
it and its links break. The output is a `.xlsx` (or a Google Sheet when Drive is
connected) plus the prebuilt site files, packaged together so the links resolve.

## What ships each run

One zip (or one Google Drive folder):

```
orosolu-leads-<date>.xlsx
sites/
  <slug>.html      ← one self-contained prebuilt site per qualified lead
  ...
```

**Default route = Google Drive** (not local). Put every run in the SAME Drive folder
**"orosolu Leads"** (folderId `1paJDGFHEJ81eqOyzP0ulhvmsEhuVB93e`) as a **separate
dated entry** — a Google Sheet titled `orosolu leads — <YYYY-MM-DD> (<area>)`. Build a
CSV with the columns below and `create_file` (contentMimeType `text/csv`) so Drive
converts it to a native Sheet; use `=HYPERLINK("url","label")` for clickable links.
One sheet per run — never overwrite prior weeks. Only if the Drive tools aren't
available in the session, fall back to a local `.xlsx` via `SendUserFile` and say it
needs manual upload.

Site links (the Website column) point to the **live hosted URL** — clicking opens the
rendered site in a new tab. Hosting is **Cloudflare Pages**: every run ships a deploy
package (a `sites/` folder — one subfolder per shop — plus `deploy.sh`) that the
operator runs on their computer (`npx wrangler login` once, then `bash deploy.sh`).
That publishes all shops to `https://<project>.pages.dev/<slug>/` in one command
(project default `orosolu-leads`). The sheet's Website cell is
`=HYPERLINK("https://orosolu-leads.pages.dev/<slug>/","Open live site ▸")`. Do NOT
link raw HTML in Drive — Drive shows raw source, not a rendered page. (Deploy is a
human step; a headless cron produces the sheet + deploy package and pings the operator
to run it.)

## Workbook tabs

1. **Read me** — run date, area, buy-box version; 3 lines on how to use it; the pitch
   (site is free when they process with orosolu/SmarterSwipe); the note that `UV` =
   unverified, confirm before quoting.
2. **Leads** — one row per qualified lead, ranked A→B→C. Columns: #, Business, Tier,
   Score, Cuisine, Address, Phone, Hours, **Payment** (flag cash/Zelle-only — no
   cards), Own-site ordering, Delivery apps, Demand (reviews·rating), **Pitch/hook**,
   Instagram, Facebook, Yelp, TikTok, Snapchat (each a clickable link or "not
   found"), Sources, and **Website** = a hyperlink ("Open site ▸") to `sites/<slug>.html`.
   Mark unverified cells `UV`. Tier cell shaded (A green / B amber / C grey).
3. **Websites** — a simple index: Business · Tier · a big "Open <shop> site ▸" link
   per lead, with a banner reminding to keep the xlsx next to the `sites/` folder.

DROP shops are not in the sheet (or listed on a separate "Skipped" tab with the
reason) — the sheet is the *actionable* list. Keep it a real spreadsheet: Arial,
frozen header, sensible column widths, no formulas needed.

## Build discipline

- Every website link must actually open its file — verify the relative path resolves
  from the xlsx location, and that the site renders (no JS errors).
- Every fact in a cell is sourced or `UV`; never invent a number to fill a column.
- The workbook is the index; the `sites/` files are the product. Ship them together.
