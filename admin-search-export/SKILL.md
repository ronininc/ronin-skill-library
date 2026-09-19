---
name: admin-search-export
description: >-
  A universal "search everything" box + full-set CSV export for any admin/CRM/portal console: one
  debounced input (220ms, ≥2 chars) that queries every record type by any identifier (name, email,
  phone, id, ticker, feed name…), guards against out-of-order responses by echoing the query,
  renders grouped typed result cards each with a contextual action (jump to record / re-invite /
  open statement), plus a one-click cookie-authed CSV export of the ENTIRE matching set (not just
  the preview) via a generated same-origin anchor. Use WHENEVER an admin surface needs "search for
  a customer/record", "find anyone by name or email", "a global search box", "look up a record",
  "export the results to CSV/Excel", "download the matching records", or "search across all our
  data". EXTENDS crm-build-standard (the admin console it sits in) and pairs with vanilla-spa-shell.
  Guardrails: server enforces the ≥2-char floor and a preview row cap (25) vs a larger export cap
  (2000); the LIKE query escapes %/_ wildcards; the stale-response guard prevents a slow earlier
  query overwriting a newer one; export rides the session cookie via a same-origin GET anchor
  (no token in the URL); results are admin-gated server-side.
---
# admin-search-export — one box to find any record, one click to export

## What it is / when to use
A debounced, multi-type record search with an inline results panel, and a CSV export of the full
matching set. Drop it into any admin/operator console where the operator needs to locate a record
fast across several tables and occasionally pull the matches into a spreadsheet.

## Reference implementation (Wavelygth — lift from here)
- **Client** — `~/Projects/clients/wavelygth/portal/index.html` L1206-1253
  - Debounce L1206-1212: `input` handler clears a timer, ignores `<2` chars, fires `runSearch(q)`
    after **220 ms**.
  - `runSearch(q)` L1213-1234: fetches `/api/admin/search?q=`; **stale-response guard** L1217 —
    `if (input.value.trim() !== d.query) return` (the server echoes the query back, so a slow
    earlier request can't clobber a newer result); renders `group()`/`row()` helpers into typed
    sections, each row carrying a contextual action button via `data-*`.
  - Result click delegation L1235-1245: `data-pf` → switch to the statement tab + select that
    record; `data-reinvite` → fire the re-invite flow. (Pattern: navigate, don't reload.)
  - CSV export L1247-1253: a `≥2`-char check, then build `<a href="/api/admin/search/export?q=…">`,
    `document.body.appendChild → click → remove`. **Same-origin GET carries the session cookie**,
    so no token goes in the URL.
- **Server** — `~/Projects/clients/wavelygth/worker/index.js`
  - `likeArg(q)` L1550 — escapes `\ % _` and wraps in `%…%`; every LIKE uses `ESCAPE '\'` (L1554).
  - `recordSearch(env, q, LIM)` L1552-1592 — one query per record type, each `… WHERE col LIKE ?
    ESCAPE '\' OR id = ? … LIMIT ?`; returns `{ results: {typeA, typeB, …}, total }`. (In
    Wavelygth some types are fanned out across shards then labelled — that's the commerce-spine
    shard router; on a single DB it's just N queries.)
  - `handleAdminSearch(env, url)` L1594-1599 — trims `q`, returns empty on `<2` chars, else
    `recordSearch(env, q, 25)` and echoes `{ query: q, … }`.
  - `csvCell(v)`/`csvRows(rows)` L1603-1607 — RFC-4180 quoting (wrap + double any `"` when the cell
    has `",\r\n`).
  - `handleSearchExport(env, url)` L1611-1631 — `recordSearch(env, q, 2000)`, flattens every type
    into rows with a leading `type` column, prepends a **UTF-8 BOM** (`﻿`) so Excel reads it right,
    returns `text/csv` + `content-disposition: attachment; filename="records-<date>.csv"`.
  - Routes L3227-3228, behind the single admin gate L3172.

## How to reapply it
1. **Server:** copy `likeArg` + the `ESCAPE '\'` convention. Write `recordSearch(env, q, LIM)` with
   one SELECT per record type you want findable, each `LIMIT ?` so a huge match can't blow up.
   Expose `/search` (LIM 25, echo the query) and `/search/export` (LIM ~2000, CSV). Copy
   `csvCell`/`csvRows` and the BOM. Both routes admin-gated.
2. **Client:** copy the debounce + stale-guard + `runSearch` renderer; give each result row a
   `data-*` action and delegate clicks to navigate in-app. Copy the anchor-download for export.

## Gotchas (from the code)
- **Echo + compare the query = the stale-response guard.** Without it, a slow "jo" response can
  land after "john" and show wrong results. The server must return `query` and the client must
  bail if it no longer matches the box.
- **Escape LIKE wildcards.** A user typing `%` or `_` (or `\`) must not turn into a wildcard —
  `likeArg` escapes them and every LIKE declares `ESCAPE '\'`.
- **Two different caps.** Preview is small (25) for speed; export is larger (2000) because it's the
  deliberate "give me everything" action. Both are bounded — never unbounded.
- **Export via same-origin anchor, not fetch+blob.** A plain `<a>` GET rides the HttpOnly session
  cookie so the CSV is auth'd without ever putting a token in the URL. (Note: in a sandboxed
  Artifact, anchor downloads are blocked — this pattern is for a real deployed origin.)
- **BOM before the CSV** or Excel mangles UTF-8 names. Quote cells per RFC 4180.
- Enforce the `≥2` floor on the SERVER too — never trust the client's minimum.
