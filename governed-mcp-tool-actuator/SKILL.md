---
name: governed-mcp-tool-actuator
description: >-
  The SAFE-CONSUMER pattern for letting an AI agent drive an EXTERNAL / untrusted MCP tool server
  (a desktop-control binary, a browser MCP, a home-automation bus, a vendor integration) without
  ever auto-firing something irreversible. Two reusable atoms: (1) a FAIL-CLOSED tool-catalog
  classifier that sorts every advertised tool into READ (auto-runs), COMMIT (must pass a human
  confirm gate), or PROHIBITED (never even mapped) from the tool NAME's verbs — a mutating verb
  beats any read-y prose, an unrecognized tool is COMMIT, and password/payment/captcha/oauth/account
  tools are refused outright as human-only; (2) a small ACTUATOR-adapter seam (read / typeDraft /
  screenshot / select / commit) that only reaches `commit()` after the host's own confirm gate says
  yes, then re-observes to VERIFY the change and never claims a landing it didn't see. Plus a stdio
  JSON-RPC MCP client that treats `initialize`+`tools/list` as LIVE discovery and degrades honestly
  to UNAVAILABLE when the external binary isn't configured. Use WHENEVER a build connects an agent to
  a third-party MCP/tool server and you must gate the dangerous tools: "let the assistant use these
  tools but confirm before it acts", "safely wrap an untrusted MCP server", "which of these tools are
  read-only?", "don't let it click/send/delete without me", "drive a device/app through MCP under a
  confirm gate." It is the CLIENT-side inverse of crm-mcp-server (which HOSTS your CRM as an MCP
  server); the COMMIT tools route through whatever confirm loop you already have —
  governed-operator-console or confirmed-inputs-decision-gate — and this does NOT rebuild that loop.
  Do NOT use it to expose your own app as a server (crm-mcp-server) or to gate an INPUT value
  (confirmed-inputs-decision-gate).
---
# Governed MCP Tool Actuator

## What it is / when to use / composes with
When you hand an AI agent a set of MCP tools you did **not** write — a native desktop-control server, a
browser driver, a smart-home bus, a partner's integration — the catalog mixes harmless perception tools
(read the screen, list state) with committing action tools (click, send, delete, run). Letting the model
decide which is safe is the failure mode. This skill is the **safe consumer**: classify the catalog
*before* invocation, auto-run only the read-only tools, and route every committing tool through the
confirm gate the client build already has.

Two atoms, both renderer/product-agnostic:
- **A fail-closed tool classifier** — verb-based `READ | COMMIT | PROHIBITED`, decided from the tool name
  (reliable for `verb`-style tool names), mutating verb wins over read-y prose, unknown ⇒ COMMIT.
- **An actuator adapter seam** — a tiny interface (`read`, `typeDraft`, `screenshot`, `select`, `commit`)
  the host's propose→confirm→commit loop drives; `commit()` is unreachable until a human said yes, and it
  verifies by re-observing.

Composes with:
- **`crm-mcp-server`** — the *inverse*. That skill HOSTS your CRM as an MCP server an external brain calls.
  This skill is the CLIENT that safely CONSUMES an external server. Same protocol, opposite direction.
- **`governed-operator-console` / `confirmed-inputs-decision-gate`** — the propose→confirm→execute→audit
  loop the COMMIT tools flow through. This skill *feeds* that gate a classified, side-effect-typed action;
  it does not re-implement the gate. (In the reference build the gate is a device-action executor with a
  before/after confirmation step — swap in whatever confirm surface the client already ships.)
- **`scoped-bearer-token` / `clearance-rbac`** — if the external MCP server needs auth, mint/scope the
  token there; don't reissue credentials in this layer.

## Reference implementation (TSS-own)
- `server/src/runtime/ghost-control-mcp-client.ts:71` — `classifyGhostTool(name, description)`: the
  fail-closed core. `PROHIBITED_RX` (line 59) refuses to map password/payment/card/captcha/oauth/
  create-account/accept-terms tools at all (human-only acts). `MUTATING_VERBS` (line 46) beats
  `READONLY_VERBS` (line 53) — so a tool whose *name* says `drag`/`window`/`run` is COMMIT even if its
  prose says "find"/"open". A name with **no** recognized verb returns COMMIT — "when in doubt, it commits."
  Each COMMIT/READ also carries a typed action-kind (send/submit/delete/click, or read/scroll/hover/focus).
- `server/src/runtime/ghost-control-mcp-client.ts:101` — `resolveGhostControlCommand()`: resolve the
  external binary from an env command (JSON array or bare path); absent ⇒ `null` ⇒ the whole capability is
  UNAVAILABLE and every surface degrades honestly instead of pretending. The binary is never bundled.
- `server/src/runtime/ghost-control-mcp-client.ts` (session class) — a persistent line-delimited JSON-RPC
  session over the server's stdio; `initialize` + `tools/list` are treated as **live observation** (you
  really discover what the server can do), and one run issues several `tools/call` over the one live child.
- `server/src/runtime/ghost-control-actuator.ts:36` — `resolveGhostToolMap(tools)`: map the live catalog to
  a fixed set of primitives (inspect/capture/activate/focus/insertText/press) by matching the tool NAME
  first, then name+description (line 29 `pick`), honoring env overrides. Names vary by server version, so
  they're resolved from the live list, never hard-coded.
- `server/src/runtime/ghost-control-actuator.ts:60` — `createGhostControlActuator(session, map, app)`: the
  adapter that implements the host's actuator interface. `commit()` (line 88) is only ever *called* by the
  executor after its gate allowed the step; it re-inspects to VERIFY and reports `landed:false` honestly if
  it can't confirm. `typeDraft` throws rather than "draft blind" when the server exposes no text-entry tool.

## How to reapply in a CLIENT build
1. **Speak the server's protocol as a client.** Stand up a small MCP client (stdio for a local binary, HTTP
   for a remote server). Call `initialize` then `tools/list` — this is your live catalog. Configure the
   endpoint/binary from env; if it's absent, mark the capability UNAVAILABLE and degrade — never fake it.
2. **Classify every tool before you let the agent touch it.** Port `classifyGhostTool`: keep the two verb
   sets and the PROHIBITED regex; a mutating verb wins, unknown ⇒ COMMIT, prohibited ⇒ don't map. Adjust the
   verb sets to the server's naming, but keep the fail-closed default.
3. **Only READ tools auto-run.** Perception/list/inspect tools the agent may call freely. COMMIT tools are
   *proposed* into your existing confirm gate (governed-operator-console / confirmed-inputs-decision-gate);
   PROHIBITED tools are surfaced to the user as "you must do this yourself."
4. **Wrap the primitives in an actuator adapter.** Resolve the catalog to your host's action interface with a
   `resolveToolMap`-style pass (name-first matching + env overrides). The host's propose→confirm→commit loop
   calls `commit()` only after a human yes.
5. **Verify after commit.** Re-observe (re-inspect / screenshot) and report only what you actually saw landed.
   Never assert a send/click/delete succeeded without re-reading the state.

## Gotchas
- **Fail closed on the crux, don't just gate it.** Password/payment/captcha/oauth tools are *not mapped at
  all* — gating them still risks a mis-fire. They are the user's to perform; refuse to wire them.
- **Classify on the NAME, not the description.** A prose blurb ("find and open…") will down-rank a real
  mutating tool. Verb-tokenize the name first; only fall back to the description for tie-breaks.
- **Unknown verb ⇒ COMMIT.** A tool you can't classify is treated as committing. This is the whole safety
  property — do not "helpfully" default unknowns to read-only.
- **Don't bundle the external binary/endpoint.** Resolve it from config; a missing server is an honest
  UNAVAILABLE, not a crash and not a pretend success. A live drive may also need OS-level grants (macOS TCC
  Accessibility, a browser extension permission) only the user can give.
- **This is the CLIENT half only.** The confirm/audit loop is a separate, pre-existing concern — compose it,
  don't fold it in here, or the skill stops being reusable across hosts.
- **Keep it out of the moat.** The value is the *classifier + adapter seam*, not any particular product's
  confirmation UI. Ship the typed contract; leave the confirmation surface to the host.
