---
name: least-privilege-mcp-connector
description: >-
  The pattern for exposing your CRM/app as an MCP server to an UNTRUSTED third-party AI assistant (a
  vendor's AI connector that trains on and monetizes whatever it sees) — giving it the LEAST that is still
  useful and NOTHING that can leak PII or change the business. Three moves: (1) a hard field ALLOWLIST view
  function that maps a full record down to a handful of non-identifying fields (name/company/status/last-
  touched — never email, phone, notes, or message bodies), so everything not explicitly returned stays in
  the CRM; (2) aggregate-only snapshots/alerts that reuse the SAME PII-free feed your oversight surface
  already computes (counts, pipeline value, severities — no names); (3) at most ONE write, scope-gated, that
  can only drop a note into the operator's capture inbox — the assistant cannot send, book, pay, edit a
  record, export, or bulk-list. Host + scope gated on every request; revoking the token cuts it off
  instantly. Use WHENEVER a build must "connect Meta AI / a partner's AI / an outside assistant to the CRM",
  "let a third-party AI look things up but not see customer data", "give a vendor connector read access
  safely", "expose a minimal MCP for an assistant I don't fully trust", or "an AI can leave me notes but
  touch nothing." It COMPLEMENTS crm-mcp-server (the full-power MCP server for a TRUSTED operator brain —
  this is its deliberately-starved sibling for an untrusted caller), scoped-bearer-token (mints/hashes/
  revokes the token — reuse it), and governance-diode (the sanitized one-way feed this reuses for
  aggregates). Guardrails: the allowlist view is the privacy boundary (default-deny every field); the lone
  write lands in an inbox for a human, never an action; each token scope is re-checked per tool.
---
# Least-Privilege MCP Connector — the most-restricted MCP surface, for an AI you don't trust

## What it is / when to use / what it composes with
A tiny MCP server mounted inside your existing Worker at its own route, built for the case where the CALLER
is an untrusted third-party AI (a platform's "AI connector", a partner's assistant) that may retain or
monetize what it reads. Where crm-mcp-server hands a trusted operator brain broad read+act tools, this hands
an untrusted caller: aggregate health, non-PII alerts, a name/company lookup reduced to a field allowlist,
and a single "leave the owner a note" write. Reach for it whenever "connect an outside AI to my data" is the
ask and the honest answer is "only the parts that can't hurt me."

**Composes with:** **crm-mcp-server** (same transport — a Zod-typed MCP server in the Worker's own D1; this
is the minimal-scope instance of it), **scoped-bearer-token** (the token store + hash + revoke — this
authenticates against it, it does not mint its own), **governance-diode** / a Kingmaker-style oversight feed
(reuse its already-sanitized aggregates instead of computing new ones that might leak), and
governed-operator-console (the human surface where the captured `[Assistant]` notes surface for action).

## Reference implementation — EXACT source
`ronininc-site/worker/muse-mcp.ts` (a `/mcp/<assistant>` route for an external AI connector):
- **The privacy boundary — the allowlist view**: `worker/muse-mcp.ts:38-46` (`museContactView` returns
  ONLY `name`, `company`, `status`, `last_touched`; email/phone/tags/notes are read from D1 but never
  returned — the comment at `:36-37` states the rule).
- Server + tools: `worker/muse-mcp.ts:48-97` (`createMuseServer`).
  - Aggregate-only, reusing the oversight feed: `business_snapshot` `:52-57` and `list_alerts` `:59-64`
    both call `statusSnapshot` / `alerts` imported from the Kingmaker oversight module (`:24`) — "totals
    only, no names."
  - `find_contact` capped + reduced: `:66-81` (`MAX_MATCHES=5` at `:27`; the SQL selects more columns but
    the response maps every row through `museContactView`).
  - The lone write, scope-gated: `capture_note` `:83-94` — refuses unless the token carries the
    `muse:capture` scope (`:89`), and only inserts a `[Assistant]`-tagged row into the `captures` inbox.
- Host + scope gate on every request: `worker/muse-mcp.ts:99-110` (`handleMuseMcp`): `ALLOWED_HOSTS` /
  `.workers.dev` check `:101` (`ALLOWED_HOSTS` at `:26`), token authenticated via the shared
  `authenticateMcp` (`:23`), and a hard `muse:read`-scope requirement `:104` before the handler mounts.
- Wiring: routed alongside the trusted MCP endpoints in `worker/index.ts:301-306` (imported `:72`).

## How to reapply — the schema + THE INVARIANT
1. Write the ALLOWLIST view FIRST: `assistantView(record) => { …only safe fields… }`. Select whatever you
   need from D1, but the response goes through this function so an added column never silently leaks.
2. Register read tools that return aggregates (reuse your oversight/diode feed) and allowlist-reduced
   lookups with a hard match cap. Annotate them honestly (`readOnlyHint:true, openWorldHint:false`).
3. Register at most ONE write, and make it inert: it lands in the operator's capture/inbox tagged with the
   assistant's name — never an action (no send/book/pay/edit/export/bulk-list). Gate it on a distinct
   scope (`assistant:capture`) separate from the read scope (`assistant:read`).
4. Gate the handler: host/Origin allowlist + the assistant's own scope required before the server even
   mounts; authenticate against the shared token store so revoking the token in Settings cuts the
   assistant off instantly.
5. **THE INVARIANT:** default-deny every field and every capability. The connector may reveal only what the
   allowlist view returns and may change only the one inbox row; anything an untrusted AI could exfiltrate
   or actuate is simply not exposed. A leaked/abused token can read non-PII aggregates + reduced lookups
   and drop notes — nothing more.

## Gotchas — real pitfalls from the code + how it's validated
- **The SQL can over-select; the response must under-return.** `find_contact` reads `email`/`phone`/`tags`
  from D1 (`worker/muse-mcp.ts:74`) but the mapping through `museContactView` (`:80`) drops them. If you
  return raw rows you leak — always map. Validated by reading the tool's response shape, not the query.
- **Reuse the PII-free aggregate, don't recompute.** `business_snapshot`/`list_alerts` call the SAME
  `statusSnapshot`/`alerts` the oversight feed uses (`:24`, `:57`, `:64`) — a hand-rolled "summary" is
  where names slip back in.
- **Scope the write separately from the read.** A single `assistant:read` scope must NOT authorize the
  capture write; `capture_note` re-checks `muse:capture` (`:89`) even though the handler already required
  `muse:read` — least privilege is per-tool, not per-connection.
- **Host-lock the endpoint.** `handleMuseMcp` refuses any host outside the allowlist (`:101`) so the
  connector can't be pointed at a look-alike; keep the allowlist tight.
- **Deployment gap to check:** the route can be wired in code yet not live in prod (this reference was
  built-and-routed but pending a prod deploy). Confirm the third party actually reaches it before telling
  the operator it's connected.
