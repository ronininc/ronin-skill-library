---
name: drive-rich-doc-generator
description: >-
  Turn a build's OWN generated artifacts into real Google Drive deliverables from inline text —
  push a whole generated site/report bundle into a Drive folder, and (the key trick) convert an
  inline HTML string into a COLORED, HYPERLINKED native Google DOC and an inline CSV string into a
  live-FORMULA Google SHEET, by uploading a tiny text payload and letting Drive import it — NO
  binary export, no Docs/Sheets batchUpdate scripting, no third-party SaaS. The mechanism is one
  Drive `files.create` multipart upload where the METADATA mimeType is the target Google-native type
  (`application/vnd.google-apps.document` / `.spreadsheet` / `.folder`) while the MEDIA part carries
  `text/html` or `text/csv`; on import Drive preserves `<table>`, `<a href>` links, inline
  `style="color:#…"` font color and `<td style="background-color:#…">` cell fills, and any CSV cell
  starting with `=` becomes a live formula. Ships the exacting plumbing: a deterministic
  collision-safe multipart boundary, a filename→mime map, OAuth-only credential resolution that
  fails HONESTLY (no API-key path exists for Drive), and a whole-bundle uploader that reports PARTIAL
  and never claims a half-delivered folder is done. Use WHENEVER a client build needs to
  "put the report/site in their Google Drive", "generate a formatted Google Doc for the client",
  "hand them a Google Sheet with the totals already formula'd", "export the proposal/SOP/ledger as a
  Doc", "email them a Drive link to a colored doc", "make a shared Drive folder of deliverables", or
  "turn this HTML/CSV into a real editable Google file". COMPLEMENTS google-oauth-connector (that mints
  and refreshes the Drive access token this consumes), and the deliverable PRODUCERS —
  printable-invoice-document, service-invoice-ledger, ventures-portfolio-rollup, content-studio-publisher,
  website-build-standard — by being the "now put it in their Drive as a native, editable file" step.
---

# Drive Rich-Doc + Formula-Sheet Generator (deliverables from inline HTML/CSV)

## What it is / when to use

A backend lane that delivers a build's own generated artifacts into a Google Drive folder, and — the
distinguishing capability — creates **native, formatted Google Docs and Sheets from small inline text
payloads** instead of uploading dead files or scripting the Docs/Sheets APIs. It exists because a
client-facing deliverable ("here's your proposal / SOP / P&L") reads far better as an **editable,
branded Google Doc** with headings, tables, links and color — or a **Sheet whose totals are live
formulas the client can re-run** — than as an attached `.html`/`.csv` blob.

Reach for it when a build produces a document or bundle and the deliverable should land in the
client's (or your agency's) Drive:
- A generated report/proposal/SOP → a colored, hyperlinked Google **Doc**.
- A P&L / pricing / roster table → a Google **Sheet** with `=SUM(...)`, `=IF(...)` cells live.
- A generated static site or a folder of files → a Drive **folder** with every file inside.

It composes ON TOP of `google-oauth-connector` (which owns the OAuth connect/callback + refresh and
hands you a `drive.file`-scoped access token) and AFTER a deliverable producer
(`printable-invoice-document`, `service-invoice-ledger`, `ventures-portfolio-rollup`,
`content-studio-publisher`, `website-build-standard`) has generated the HTML/CSV/file set.

## The mechanism (the part worth stealing)

Google Drive's `files.create` will **import and convert** an uploaded text payload into a native
Google file when you set the request **metadata `mimeType` to the target Google-apps type** while the
uploaded **media part** stays the source text type. No `disableConversionToGoogleType`, no Docs
`batchUpdate`, no Sheets `values.update` — just one multipart upload:

| You want | metadata `mimeType` | media part `Content-Type` | media body |
|---|---|---|---|
| Colored, linked **Doc** | `application/vnd.google-apps.document` | `text/html` | your HTML string |
| Live-formula **Sheet** | `application/vnd.google-apps.spreadsheet` | `text/csv` | your CSV string |
| Empty **folder** | `application/vnd.google-apps.folder` | *(none)* | *(none — JSON metadata only)* |

On HTML→Doc import Drive **preserves**: `<table>`, `<a href>` hyperlinks, inline
`style="color:#…"` font color, and `<td style="background-color:#…">` cell fills. On CSV→Sheet
import, **any cell whose text starts with `=` becomes a live formula** (`=SUM(C9:C13)`,
`=C14-C24`, `=IF(C14=0,"","…")` all work). This is the entire trick: a ~1 KB text payload yields a
fully formatted native file, sidestepping the small inline-upload cap that blocks real binaries
(zips/images/pptx).

## Reference implementation (TSS-own source)

`server/src/runtime/google-drive-write.ts` — the whole multipart-write lane. The conversion is a
one-field extension of this exact upload builder; the folder path below already sets a native
`google-apps` metadata mimeType, so Docs/Sheets are the same move with a different target type.

- **`buildMultipartBody(metadata, content, mimeType, boundary)`** — `google-drive-write.ts:124`.
  Drive's `multipart/related` framing is exacting (metadata part → media part → closing boundary,
  CRLF-delimited). This assembles it correctly.
- **`safeBoundary(content)`** — `google-drive-write.ts:149`. A **deterministic** boundary that is
  regenerated (suffix `-1`, `-2`, …) until it cannot appear inside the content. A random boundary
  that happened to collide would silently corrupt the upload; deterministic means the same input
  produces the same request.
- **`mimeTypeFor(fileName)`** — `google-drive-write.ts:109`. Filename→real mime map with a safe
  `application/octet-stream` default, so Drive renders a site file instead of forcing a download.
- **`resolveDriveCredentials(env)`** — `google-drive-write.ts:46`. Drive has **no API-key path**;
  absence of an OAuth token is a config FACT to report, never worked around. Names the exact missing
  var and the narrow `drive.file` scope (the scope that only touches files this app itself creates).
- **`uploadFile(input)`** — `google-drive-write.ts:166`. Builds `{ name, mimeType, parents }`
  metadata (`:190`) and POSTs the multipart body. Gates success on a returned file **id**: a `2xx`
  with no id is reported as NOT done (`:219`) — the fake-success trap.
- **`createFolder(input)`** — `google-drive-write.ts:236`. Creates a **native** folder via JSON-only
  metadata `mimeType: application/vnd.google-apps.folder` (`FOLDER_MIME`, `:106`). This is the proof
  the conversion-by-metadata mechanism already works in this code — Docs/Sheets just swap the type.
- **`uploadGeneratedSite(input)`** — `google-drive-write.ts:289`. Folder-first, then every file;
  flattens nested paths (`content/brief.json` → `content__brief.json`) so nothing collides; reports
  **PARTIAL** (`:328`) and returns `performedWork:false` unless EVERY file landed — a half-uploaded
  folder is never announced as "it's in Drive".

Proof: `tests/google-drive-write/run.ts` (10/10) — GD-02 asserts the media part carries the real
mime, GD-03 the fake-success trap, GD-05 boundary can never collide, GD-07 folder-created-first with
nested paths preserved, GD-08 PARTIAL is never reported as done.

## How to reapply (in a CLIENT build)

1. **Get a token.** Use `google-oauth-connector` to connect the client/agency Google account and
   obtain a `drive.file`-scoped access token. Resolve it the way `resolveDriveCredentials` does —
   fail honestly if absent.
2. **Author Doc-OPTIMIZED HTML, not your web HTML.** Import treats the HTML as a *document*, not a
   web page: semantic `<h1>/<h2>/<h3>` become Docs heading styles + outline; a dark-CSS site with JS
   charts imports as garbage. Use tables for callouts (a 1-cell table with `background-color`),
   `<a href>` for links, and inline `style="color:#…"`. A readable palette on white: green
   `#188038` / fill `#e6f4ea`, red `#d93025` / fill `#fce8e6`, a deep-gold label `#8a6a1c`.
3. **Create the Doc:** call the upload with metadata `mimeType:'application/vnd.google-apps.document'`
   and the media part `text/html` + your HTML string. (Same `buildMultipartBody`/`uploadFile`
   plumbing; just override the metadata mimeType instead of deriving it from the filename.)
4. **Create the Sheet:** metadata `mimeType:'application/vnd.google-apps.spreadsheet'`, media part
   `text/csv` + your CSV. Put formulas straight in cells as `=SUM(...)`. **CSV-quote any formula
   containing commas or quotes**, doubling inner quotes: `"=IF(E4=0,"""",E4/D4)"`.
5. **Bundle deliverables:** `uploadGeneratedSite` for a folder + files; or `createFolder` then loop
   `uploadFile` for a mixed set of Docs/Sheets/raw files under one shared folder.
6. **Share the link, don't lie about it.** Only report the `webViewLink` when `performedWork` is
   true; surface PARTIAL honestly. Hand the returned link to `send-once-idempotent-email` /
   `governed-email-outreach` if the client should be emailed the deliverable.

## Gotchas

- **Conversion needs the metadata mimeType set to the TARGET type.** If you leave metadata mimeType
  as `text/html` (what `mimeTypeFor` returns), Drive stores a **raw HTML file**, not a Doc — the
  reference `uploadFile` does exactly this for site files on purpose. To convert, override it.
- **`drive.file` scope only sees files this app created.** It can create Docs/Sheets/folders and edit
  what it made; it cannot read or reparent files it didn't create. MOVE/reparent into a folder owned
  by another account is owner-gated even though CREATE inside it is not.
- **No ownership transfer.** A programmatic share tops out at `writer` (reader/commenter/writer);
  there is no `owner` role and no trashing another owner's file. To get files truly owned by another
  account, create them AS that account. Granting `writer` gives full edit but ownership stays put.
- **The connector can't edit a Doc in place across runs** the way this file works — a rebuild creates
  a NEW file with a new id. If you need stable identity, find-by-title-in-parent (or move to a
  Docs/Sheets `batchUpdate` lane), don't assume the id persists.
- **Boundary must be deterministic and collision-checked.** Don't drop in a random UUID boundary; if
  it ever appears in the content the upload silently corrupts. Keep `safeBoundary`'s regenerate loop.
- **Verify structure, not color, in tests.** A text export of an imported Doc shows markdown-escaped
  `\*\*bold\*\*` and can't render color — assert on tables/links/headings surviving; color rendering
  is inferred from standard import behavior.
- **Wire this to your own build's outbound-allow / online-mode switch** before it fetches Google, and
  gate on the returned file `id` — treat a `2xx` with no id as NOT done.
