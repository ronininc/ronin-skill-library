---
name: agnostic-import-parser
description: >-
  Client-side "upload your existing list" intake for any CRM/portal/list-builder — auto-detects and
  parses CSV / TSV / semicolon / JSON in the browser (BOM-stripped, delimiter sniffed by header
  counts, quote-aware), shows a header + preview table, then POSTs the rows to a server ingest that
  case-insensitively auto-matches columns (name/email/phone/company…) and de-dupes by email. Use
  WHENEVER a build needs "import my existing customers/investors/leads", "upload a spreadsheet",
  "bring in my list", "onboard from a CSV/Excel export", "paste in JSON", or a bulk "add records
  from a file" step. EXTENDS crm-build-standard (the record store it feeds) and pairs with cf-forms;
  the parser is pure/portable — only the final POST target and the server's record kinds are
  app-specific. Guardrails: 4 MB client guard + a server row cap (structured import only — binary/
  unstructured files degrade honestly to "store it as a file feed", see chunked-uploader /
  data-feed-intake); de-dupe by email, never overwrite; imported accounts get an UNUSABLE password
  until separately invited (never a real login on import).
---
# agnostic-import-parser — "upload your list", any format

## What it is / when to use
A two-part capability: (1) a pure browser parser that reads a dropped/picked file of unknown type
into an array of row-objects, previews it, and (2) a server endpoint that turns those rows into
records (contacts/investors/leads), de-duping by email. Use it as the "import my existing data"
onramp on any CRM/portal. It is format-agnostic by *sniffing*, not by asking the user what they have.

## Reference implementation (Wavelygth — lift from here)
- **Client parser + UI** — `~/Projects/clients/wavelygth/portal/index.html`
  - `parseDelimited(text, d)` L1258-1273 — a hand-rolled, quote-aware delimited parser (handles
    `""` escaped quotes, `\r\n`, trailing field), returns row-objects keyed by trimmed headers.
  - `parseAgnostic(text)` L1274-1290 — strips a UTF-8 BOM, tries `JSON.parse` first when the text
    starts with `[`/`{` (accepts a top-level array, a `{rows:[…]}` envelope, or a single object),
    else sniffs the delimiter by counting `,` vs `\t` vs `;` in the **first line** and picks the
    winner. Returns `{format, rows}`; `format` is one of `JSON|CSV|TSV|semicolon|unknown|empty`.
  - `handleImportFile(file)` L1291-1313 — 4 MB size guard, `FileReader.readAsText`, caps at 5000
    rows, renders a header row + first-5 preview, or an "unreadable — store it in Feeds instead"
    message when nothing parsed.
  - Dropzone + pick + run wiring L1314-1332 (`importRows` buffer, POST on Run).
- **Server ingest** — `~/Projects/clients/wavelygth/worker/index.js`
  - `handleImport(req, env, me, url)` L1642-1701 — `IMPORT_MAX_ROWS = 5000` (L1640); a
    `pick(row, keys)` closure L1651-1657 that normalizes every header (`trim().toLowerCase()
    .replace(/[\s_-]+/g,'')`) and matches against a list of accepted spellings; de-dupes by email
    (`SELECT id … WHERE email=?`), inserts with an **unusable random password hash** so the account
    can't be logged into until separately invited; reports `{created, skipped, errors}`.
  - Route: L3229 `if (path === '/api/admin/import' && method === 'POST') return handleImport(...)`,
    behind the single admin gate at L3172 (`if (!requireAdmin(me)) return bad('Admin only.', 403)`).

## How to reapply it
1. **Client:** copy `parseDelimited` + `parseAgnostic` verbatim (zero deps, pure). Wire a dropzone
   → `FileReader.readAsText` → `parseAgnostic` → preview table → keep `rows` in a buffer → POST
   `{ target, rows }` to your ingest on confirm. Keep the 4 MB guard and the row cap.
2. **Server:** copy the `pick(row, keys)` normalizer — it is what makes column matching survive
   "Email Address", "e-mail", "Phone Number", "Company Name" etc. For each target record type,
   list the accepted header spellings once. De-dupe on your natural key (email). Cap rows
   server-side too (never trust the client cap). Wrap `readJson` in try/catch and return a friendly
   "too large / couldn't read" message.
3. **Records:** on a contact/investor import, insert with a random unusable password + `source =
   'import'`, then hand off to your invite flow (cf-identity) — do NOT set a usable credential from
   an imported row. For lead imports, run them through your existing scorer before insert so
   imported leads rank alongside captured ones.

## Gotchas (from the code)
- **Sniff the FIRST line only** for the delimiter — a body cell containing commas won't skew the
  header count. JSON is tried before delimited, so a `.json` list never gets mis-read as CSV.
- **Strip the BOM** (`/^﻿/`) before anything — Excel's "CSV UTF-8" export prepends one and it
  poisons the first header key otherwise.
- **The parser is for STRUCTURED data only.** Binary/opaque files (PDF, images, zips) return
  `rows: []`; the UI must degrade honestly to "store this as a file" (see `chunked-uploader` /
  `data-feed-intake`) rather than silently importing zero rows as success.
- **Never overwrite on collision** — an existing email is a `skipped++`, reported back, not an
  update. Import is additive.
- Match headers case-insensitively AND after stripping spaces/`_`/`-`; real spreadsheets are messy.
- Enforce the row cap on BOTH ends and the body-size cap in `readJson` — a 5000-row JSON body is
  large; size it deliberately (Wavelygth allows a 2 MB import body).
