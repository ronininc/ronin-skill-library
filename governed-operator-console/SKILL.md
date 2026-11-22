---
name: governed-operator-console
description: >-
  An in-CRM chat where an LLM operator is grounded ONLY in a live CRM snapshot, must answer as strict JSON
  {reply, proposal}, may propose AT MOST ONE whitelisted action, and NEVER acts — a separate execute
  endpoint re-validates every parameter itself, runs the action, and writes an audit note. The propose →
  human-confirm → execute → audit loop is the cage; the model is just the animal in it. Use WHENEVER a
  build wants "an AI that can run the CRM but can't go rogue", "chat to my CRM and have it do things",
  "an assistant behind a confirm gate", "Solomon Lite in the admin", "let the AI move deals / pause
  campaigns but I approve first", or "an operator console." It COMPLEMENTS crm-mcp-server (that exposes
  the CRM to an EXTERNAL brain over MCP; this is the WEB operator surface inside the admin — different
  entry point, same governance philosophy), append-only-audit-log (every executed action is logged — reuse
  it), and a pluggable draft-brain helper (the swappable Codex/ChatGPT/self-hosted/Workers-AI model — do
  NOT hardcode a provider). Guardrails: the executor NEVER trusts the model's params (re-fetches + re-checks
  every id and enum), the action list is a closed whitelist, money/irreversible stays off it, and no action
  runs without an explicit human click.
---
# governed-operator-console — the AI proposes, the operator confirms, the code decides

Give an operator a chat box that can actually run the business, without giving the model the keys. The
brain sees a compact, real snapshot of the CRM and nothing else; it may suggest exactly one action from a
fixed list; a human clicks Confirm; and a separate executor — which trusts none of the model's output —
validates and runs it, then logs it. An uncensored/jailbroken brain still can only do what the whitelist
and the confirm gate allow.

## What it is / when to use
The web-native operator surface for a CRM. Reach for it when the deliverable is "talk to the CRM and have
it do a few safe things under supervision." It is deliberately narrow: a handful of whitelisted actions,
one proposal per turn, human confirm mandatory.

**Composes with:** **crm-mcp-server** (the OTHER way to let a brain drive the CRM — over MCP, for an
external agent; this console is for a human operator in the admin UI. Same "propose, don't act" doctrine,
different transport. Build both if you want both.), **append-only-audit-log** (the executor writes a
timeline note per action — reuse that log, don't invent one), and a **pluggable draft-brain** helper that
tries providers in order (self-hosted → Anthropic → OpenAI → Workers AI) so it works with zero keys.

## Reference implementation (ronininc — read these)
- **The whole loop** — `worker/solomon-console.ts:1-129`. Specifically:
  - `snapshot(env)` (`:22-41`) — the ONLY facts the brain may use: counts by status, pipeline with deal
    value, unread replies, campaigns, queued recipients, partners, revenue. No raw PII dumps.
  - `ACTIONS` (`:43-48`) — the whitelist string embedded in the system prompt.
  - `solomonConsoleChat` (`:50-78`) — builds the strict-JSON system prompt, calls the brain, and parses
    `{reply, proposal}` out of the model text (regex-extract a JSON object, tolerate junk around it).
  - `solomonConsoleExecute` (`:82-129`) — the executor: per action it RE-fetches the stage/deal/contact,
    RE-checks the enum, runs the mutation, and `audit()`s it. Unknown/non-whitelisted action → rejected.
- **Routes** — `worker/admin.ts:387-388` (`POST solomon/chat`, `POST solomon/execute`), under the gated
  `/api/admin/*` block so only a staff session reaches them.
- **UI** — `public/admin/admin.js:118-150`: a chat thread, and for a proposal a card showing the action +
  rationale + params with **Confirm & run** / **Dismiss** buttons; confirm POSTs to `solomon/execute`.

## How to reapply it
1. **Snapshot function** — one `Promise.all` of small aggregate queries returning a compact object. This is
   the model's entire world; keep it factual and small (counts, ids + names for things it can act on, a few
   totals). Do not stream raw contact rows.
2. **Whitelist** — a short list of safe actions, each with an explicit param shape, written into the system
   prompt. In the reference: `move_deal`, `set_contact_status`, `outreach_control`, `send_all_outreach`,
   `create_partner`. Nothing that moves money or is irreversible.
3. **Chat endpoint** — system prompt says: reason ONLY from the snapshot, never invent records/numbers,
   propose at most ONE action when clearly warranted else none, NEVER claim you acted, and reply with STRICT
   JSON `{"reply": string, "proposal": null | {action, params, rationale}}`. Call the draft brain; extract
   the JSON with a `/\{[\s\S]*\}/` match and tolerate parse failure by falling back to raw text as `reply`.
   Return `{reply, proposal, provider}`.
4. **Execute endpoint** — the security boundary. For each whitelisted action: read `action` + `params` from
   the request, then INDEPENDENTLY validate — re-fetch the target row by id (404 if gone), re-check every
   enum against your own allowed set, and only then run the mutation. Write an audit row
   (`activities`/timeline, actor = the console). Anything not in the whitelist → `bad('Unknown or
   non-whitelisted action.')`.
5. **Brain gate** — if no brain is configured, return 503 with an actionable message; never fake a reply.
6. **UI** — chat thread; render a proposal as a card (action, rationale, pretty-printed params) with
   Confirm & run + Dismiss. Confirm calls execute and shows the result inline; nothing runs without it.

## Gotchas (from the code)
- **The executor must re-derive everything.** It re-`SELECT`s the stage to get its name, re-`SELECT`s the
  deal to get its contact_id, re-checks the status enum — it treats the model's params as an untrusted
  request, identical to a raw API call. This is the actual safety property; a thin executor that trusts
  `params` defeats the whole design.
- **One proposal, human confirm, no self-execution.** The chat endpoint has no write path at all — it can
  only return a proposal. Keep those two endpoints separate; don't let "chat" run anything.
- **Ground truth or nothing.** The system prompt forbids inventing contacts/deals/numbers and forbids
  claiming an action was taken. The snapshot is the leash — if a fact isn't in it, the model shouldn't
  state it.
- **Parse defensively.** Models wrap JSON in prose or code fences. Extract the first `{...}` block and, on
  failure, degrade to showing the raw text as the reply with `proposal: null` — never 500 on bad JSON.
- **Keep money and irreversible off the whitelist.** `send_all_outreach` is bounded by the daily cap and
  still human-confirmed; there is deliberately no "send payment" action. Add only reversible, bounded
  actions.
- **Provider-agnostic brain.** Route through a helper that falls back across providers (works with zero
  keys via Workers AI) so the console isn't hostage to one API key — that helper is its own skill; wire it,
  don't hardcode Anthropic/OpenAI here.
