---
name: pluggable-draft-brain
description: >-
  One tiny helper a Cloudflare Worker + D1 CRM calls whenever it needs a model to DRAFT text (never to
  act): it tries LLM providers in priority order with automatic fallback — a self-hosted
  OpenAI-compatible endpoint (vLLM/Ollama/sovereign) → Anthropic Claude → OpenAI → the built-in
  Cloudflare Workers AI — so the feature works with ZERO keys and silently upgrades the moment a key
  is set, and reports WHICH provider answered. Use WHENEVER a build needs "AI-drafted" text without
  hard-wiring one vendor: "draft a reply/caption/email", "add an AI writer", "make the model
  swappable", "fall back if the API key is missing", "use my own local model", "which model wrote
  this". This is the swappable draft SEAM under other features — it is the brain BEHIND
  social-dm-inbox (DM reply drafts) and a governed-operator console (strict-JSON proposals), and the
  optional caption writer for content-studio-publisher and article author for auto-blog-network. Do
  NOT re-implement per-vendor fetch/parse/timeout logic in those skills — call this one helper and
  pass a system + user prompt. It COMPLEMENTS scoped-bearer-token (keys are Worker secrets, same
  never-in-D1/never-logged discipline). Guardrails: the brain has NO action of its own — it only
  returns text; sending/approval always stays with the human + a governed send path; every provider
  call is bounded (256 KB reader), timed out, and empty-response-guarded, and a bad key/model falls
  through to the next provider instead of breaking the feature.
---
# Pluggable Draft Brain — a swappable, fallback LLM seam for governed drafting

A ~140-line module (`draftWithBrain`) that any CRM feature calls to get DRAFTED text. It prefers the
operator's own accounts, degrades to a free built-in model, and never becomes an actor: it returns a
string and the name of the provider that produced it — nothing more. Sending, posting and approval
stay with the human and the feature's own governed send path.

**When to use:** any feature that needs model-written text (replies, captions, proposals, articles,
summaries) but should NOT be married to one vendor or break when a key is absent. **What it composes
with:** it is the seam UNDER `social-dm-inbox` (reply drafts) and a governed operator console
(strict-JSON action proposals), and the optional writer for `content-studio-publisher` (captions) and
`auto-blog-network` (articles — though that skill's reference calls `env.AI` directly). Pairs with
`scoped-bearer-token` for secret discipline.

## Reference implementation (ronininc-site — OPEN these)
- **`worker/brain.ts:1-143`** — the entire seam:
  - `boundedText` (19-35 — 256 KB streaming cap) and `jsonOf` (37-40).
  - Per-provider adapters, each returning trimmed text or throwing:
    `viaAnthropic` (42-59 — `/v1/messages`, 30 s timeout), `viaOpenAI` (61-79 — chat/completions,
    30 s), `viaWorkersAI` (81-90 — `env.AI.run('@cf/meta/llama-3.1-8b-instruct')`),
    `viaCustom` (95-114 — any OpenAI-compatible base URL, 45 s timeout, optional bearer).
  - `draftWithBrain` (121-134 — builds the provider chain in priority order, falls through on any
    error, throws `NO_BRAIN` if none configured, returns `{ text, provider }`).
  - `brainConfigured` (136-143 — `{ ready, providers[] }` for a readiness panel).
- **Env secrets (all optional):** `BRAIN_BASE_URL` (+ optional `BRAIN_API_KEY`) for a self-hosted
  endpoint, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `BRAIN_MODEL` (overrides the default per provider),
  and the `AI` Workers-AI binding. See `worker/types.ts:47-72`.
- **Real callers (how a feature uses it):**
  - `worker/social-messaging.ts:296-304` — builds a `system` + `user` prompt from a DM transcript,
    `draftWithBrain(env, system, user, 300)`, strips surrounding quotes, returns the draft +
    provider. Error mapping (317) surfaces `NO_BRAIN` as an actionable message.
  - `worker/solomon-console.ts:55,65` — `brainConfigured` gate first (503 if not ready), then
    `draftWithBrain(env, system, user, 700)` demanding STRICT JSON `{reply, proposal}`; the caller
    extracts the JSON and NEVER lets the brain execute the proposal.

## How to reapply it into a client CRM build
1. **Module.** Copy `worker/brain.ts` verbatim — it is self-contained (only imports `Env`) and has no
   DB or route of its own.
2. **Env types.** Add the optional fields to your `Env` (`brain.ts` reads
   `BRAIN_BASE_URL`/`BRAIN_API_KEY`/`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`BRAIN_MODEL`/`AI`). Set the
   Workers-AI binding `"ai": { "binding": "AI" }` so there's always a zero-key fallback.
3. **Call it from a feature.** Never call a vendor SDK directly — build a `system` (role + hard
   guardrails: "never invent facts/prices/quotes", output format) and a `user` (the grounded context),
   then `const { text, provider } = await draftWithBrain(env, system, user, maxTokens)`. Post-process:
   strip stray quotes, and if you need structured output, demand STRICT JSON in the system prompt and
   parse defensively (see the console caller).
4. **Readiness UI.** Call `brainConfigured(env)` to show which providers are live; surface `NO_BRAIN`
   as "Add ANTHROPIC_API_KEY / OPENAI_API_KEY / BRAIN_BASE_URL, or enable Workers AI."
5. **Keep the human gate.** The brain returns text only. The feature must store it as a DRAFT and
   require an explicit human confirm before any send/post/execute — this seam is deliberately
   incapable of acting.
6. **Wire it where the reference doesn't (optional deltas).** `content-studio-publisher` captions are
   manual and `auto-blog-network` calls `env.AI` directly; to unify authorship under this seam, add a
   draft endpoint in those features that calls `draftWithBrain` instead.

## Gotchas (from the code)
- **Fallthrough order is fixed and intentional:** self-hosted `custom` → `claude` → `chatgpt` →
  `workers-ai`. Any provider throwing (bad key, model error, timeout, empty response) advances to the
  next; only if ALL configured providers fail does `draftWithBrain` throw the last error. A missing
  key isn't an error — that provider is simply not added to the chain.
- **`NO_BRAIN` vs `BRAIN_FAILED`:** `NO_BRAIN` means nothing is configured (not even `env.AI`) — a
  config problem, surface it as such (503). `BRAIN_FAILED`/a provider error string means everything
  configured failed at runtime — a transient/credential problem.
- **Every read is bounded (256 KB) and every call is timed out** (30 s hosted, 45 s self-hosted).
  Don't remove these — an unbounded provider response or a hung self-hosted endpoint would otherwise
  stall a Worker request or cron tick.
- **Empty responses are treated as failures** (each adapter throws `'… empty'` on blank output) so a
  provider that returns 200-but-nothing falls through instead of yielding an empty draft.
- **Keys are Worker secrets, used only in auth headers, never logged or returned.** The brain never
  echoes a key; a readiness check reports presence (`providers[]`), never values. Preserve that.
- **The brain must never gain an action.** This is doctrine, not style: it drafts, a human confirms, a
  separate governed path sends/executes. If you're tempted to let it "just send the obviously-fine
  reply," that belongs behind a graduated-autonomy tier in the CALLING feature — never inside this
  helper.
- **Model overrides are per-deployment via `BRAIN_MODEL`**, applied across whichever provider answers
  (Anthropic/OpenAI/custom read it; Workers AI is pinned to its default). Set it deliberately — a
  model name valid for one provider will error on another and force a fallthrough.
