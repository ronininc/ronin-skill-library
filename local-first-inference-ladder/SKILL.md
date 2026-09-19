---
name: local-first-inference-ladder
description: >-
  One reasoning helper any AI-powered client app calls when it needs a model to THINK/answer: it runs
  a tiered ladder — Tier 0 a self-hosted/local model (Ollama or any OpenAI-compatible endpoint, zero
  cost, zero egress, the DEFAULT), Tier 1 a capable non-premium cloud "overflow booster", Tier 2 a
  secondary cloud backup — and escalates up the ladder ONLY when the tier below FAILS or returns an
  UNUSABLE answer (a quality/length threshold, not just a thrown error). Reserve your premium/paid
  model as last-resort authority outside the ladder so bulk work never burns premium spend. Every
  cloud tier sits behind a fail-closed EGRESS GATE (a caller "sensitive" flag + a secret/PII scanner)
  so private data never leaves the box on the overflow lane, and every escalation is audited with the
  tier + reason so an answer can be labeled local vs cloud-assisted. Use WHENEVER a build needs
  model reasoning that should "try my own/local model first", "only hit the cloud when local can't
  cope", "fall back across providers", "don't burn my paid API on easy stuff", "never send customer
  data to a cloud model", "which tier answered", or "keep it working with zero keys". COMPLEMENTS
  pluggable-draft-brain: that is the simpler DRAFT-only try-order (custom→claude→openai→workers-ai,
  advance on thrown error, returns text) — THIS is the fuller LADDER delta: local-first default,
  escalate on unusable-not-just-thrown, an overflow-budget/egress gate in front of every cloud tier,
  per-tier kill-switches, and audit of which tier answered. Use draft-brain for "write me text"; use
  this for "reason for me, cheaply and privately, upgrading only when forced". Pairs with
  scoped-bearer-token (provider keys as env secrets) and connector-egress-circuit-breaker (bound each
  cloud tier's transport). Guardrail: this returns text + provenance only — it never acts; sending or
  executing stays with the caller's own governed path.
---
# Local-First Inference Ladder — a pluggable multi-model overflow + fallback router

A ~160-line router (`runReasoningWithFallback`) any AI feature calls to get a REASONED answer without
marrying one vendor and without leaking data or money. It prefers a self-hosted/local model, only
overflows to the cloud "when tokens are absolutely necessary", never egresses sensitive content, and
reports which tier answered. It returns a string + provenance — it never sends, posts, or executes.

**When to use:** any feature that needs a model to answer/reason (a self-inspection, a summary, a
grounded Q&A, a synthesis step) where the default should be your OWN cheap local model and the cloud
is a graduated fallback, not the workhorse. **Delta vs `pluggable-draft-brain`:** draft-brain is a
flat try-order that advances only on a *thrown* error and is aimed at drafting *text*; this ladder
adds (1) a local-FIRST default tier, (2) escalation on an *unusable* answer (length/quality gate),
not just an exception, (3) an overflow-budget + egress gate guarding every cloud tier, (4) per-tier
kill-switches and an `allowEscalation` force-local flag, and (5) an audit trail of which tier
answered and why it escalated. Capture only that delta — don't re-implement the flat try-order.

## Reference implementation (TSS-own source — OPEN these)
- **`server/src/runtime/inference/reasoning-router.ts:84-158`** — `runReasoningWithFallback`, the
  whole ladder:
  - Types/options `:26-69` — `ReasoningTier = 'local' | <booster> | <backup>`, and
    `ReasoningOptions` (`minAcceptableChars`, `allowEscalation`, `containsSensitiveData`, per-tier
    model/timeout overrides, `purpose` for the audit line).
  - Tier 0 local attempt + usable test `:99-106` — a local answer is USABLE only when `ok`, no
    error, AND `text.length >= minChars`; usable → return `tier:'local', escalated:false` (zero
    egress, zero cost). `DEFAULT_MIN_CHARS = 20` at `:71`.
  - Failure-reason derivation `:108-112` — `local-error:…` / `local-empty` /
    `local-too-short:N<min` — carried up as the escalation reason.
  - `allowEscalation` force-local + "no overflow provider" short-circuit `:114-118`.
  - **Egress gate `:120-130`** — the overflow-budget guard: a caller `containsSensitiveData` flag
    OR an `assessEgressSafety(prompt)` trip refuses ALL cloud tiers and keeps the (failed) local
    result; the refusal is audited.
  - Tier 1 overflow booster `:132-143` and Tier 2 backup `:145-154` — each: call provider, audit the
    escalation, accept only if `ok && text>=minChars`, else fall through / return the failure.
  - Dependency-injection test seam `:62-69` (`ReasoningDeps`) so the ladder is unit-testable with no
    Ollama/cloud/network.
- **Provider adapters (interchangeable OpenAI-compatible clients):**
  - `server/src/runtime/inference/kimi-provider.ts` — the overflow booster: `isKimiConfigured` +
    global kill-switch + loopback-proxy detection `:37-40`, `runKimiReasoning` POSTs
    `{base}/chat/completions` with an optional `Bearer` key, `AbortController` timeout, HTTP/empty
    guards `:59-116`. `isLoopbackBase` `:29-33` — a `localhost` base = a signed-in local proxy that
    needs NO per-request key.
  - `server/src/runtime/inference/nim-provider.ts` — the secondary cloud backup, byte-for-byte the
    same shape (`isNimConfigured:24-27`, `runNimReasoning:54-109`), proving providers are swappable
    by config alone.
- **`server/src/runtime/inference/egress-guard.ts:57-65`** — `assessEgressSafety`: fail-closed
  secret/PII scanner (`RULES:17-28` — PEM keys, AWS/OpenAI-style keys, JWT, bearer, labelled
  secrets, SSN) + a Luhn-checked credit-card test (`:33-54`) so ordinary long numbers (timestamps,
  ids) don't false-trip. On any match → `{safe:false}` and nothing egresses.
- **Coding-lane variant — `server/src/runtime/coding/coding-providers.ts:243-257`** —
  `createDefaultCodingRegistry`: the same idea expressed as a REGISTRY of providers with
  `available()`/`handles()` predicates and a fail-closed external lane (`externalOptionalProvider`
  `:151-241`, OFF by default, "never a hidden fallback"). Use this shape when tiers differ in
  *capability* (deterministic generator vs. model) rather than just quality.
- **Real callers (how a feature wires it):**
  - `server/src/runtime/route-dispatch.ts:1702-1712` — the canonical pattern: **derive**
    `containsSensitiveData` by scanning the actual content (`scanForCustomerData(...).length > 0`),
    gate `allowEscalation` on it, and keep a deterministic fail-safe when no tier produces a usable
    answer (`:1715-1720`).
  - `server/src/runtime/governed-conversation-service.ts:1167,1280,1338` and
    `server/src/intelligence/informational-engine.ts:667` — the router injected as the default
    reasoner behind higher-level features.
- **Proof harness — `tests/inference-ladder/run.ts:1-203`** — asserts the locked behavior with
  injected fakes (no network): usable local never escalates, fallback fires only on fail/empty AND a
  configured tier AND escalation allowed, and the egress gate refuses secret/PII/flagged content.

## How to reapply it into a client build
1. **Copy the router + adapters + gate.** `reasoning-router.ts`, one provider adapter per tier
   (clone `kimi-provider.ts` / `nim-provider.ts` — they are self-contained OpenAI-compatible
   clients), and `egress-guard.ts`. Rename tiers to your stack, e.g.
   `type Tier = 'local' | 'overflow' | 'backup'`.
2. **Wire the tiers by env, not code.** Local = your Ollama / self-hosted OpenAI-compatible base
   (default, no key). Overflow booster = a capable, cheap cloud model (any OpenAI-compatible
   `/chat/completions` + `Bearer`). Backup = a second cloud provider. A tier is "configured" only
   when its key is present (or its base is loopback) AND its kill-switch env isn't `0` — so the
   feature works with ZERO keys (local-only) and upgrades the moment a key is set.
3. **Reserve premium OUTSIDE the ladder.** Do NOT put your paid/frontier model in the auto-escalation
   chain. The ladder exhausts cheap local + overflow tiers first; premium is a deliberate last-resort
   authority the caller invokes explicitly, so bulk reasoning never silently bills premium.
4. **Set the usable-answer bar.** Pass `minAcceptableChars` for the task (a one-line status vs. a
   paragraph). A local reply below it is a "face-plant" that escalates — this is the key win over a
   thrown-error-only fallback: a model that returns 200-but-garbage still advances the ladder.
5. **Gate every cloud tier on egress.** ALWAYS pass `containsSensitiveData` derived from a real scan
   of the content you're about to send (not a static guess), and keep `assessEgressSafety` as the
   backstop. When either trips, the ladder stays local and returns the local (possibly failed)
   result — sensitive data never rides the overflow lane. Extend the `RULES` list with your domain's
   PII shapes (CRM ids, member numbers).
6. **Audit + label.** Log each escalation with `purpose`, the failure reason, tier, model, latency.
   Surface `escalated` / `tier` in the UI so a user can see "answered locally" vs "cloud-assisted".
7. **Always have a deterministic floor.** The ladder can legitimately return `ok:false` (all tiers
   failed, or everything blocked by the egress gate). The caller must fall back to a non-model,
   file-/DB-grounded answer so the feature is NEVER silent (see the route-dispatch caller).
8. **Keep the DI seam.** Preserve `ReasoningDeps` so tests inject fake tiers — you can prove the
   local-first, escalate-on-unusable, and egress-refusal branches with no Ollama and no network
   (mirror `tests/inference-ladder/run.ts`).

## Gotchas (from the code)
- **Escalation is a FALLBACK, never a default.** A caller *preferring* the cloud is not evidence
  local can't cope: the router ALWAYS runs the bounded local attempt first, and a legacy `preferNim`
  hint cannot bypass it (`:58-59, :99-101`). Don't "optimize" by skipping local for speed — that
  reintroduces the cost/egress you built this to avoid.
- **"Usable" ≠ "returned".** Escalation triggers on `!ok || error || text.length < minChars`. An
  empty or too-short 200 response is a failure and falls through (`:102-112`). Don't treat any 200 as
  success.
- **The egress gate is fail-CLOSED and covers ALL cloud tiers at once** (`:120-130`). A false
  positive costs only "stay local this turn"; a false negative leaks data — so keep it conservative.
  The credit-card rule uses a Luhn check, not a digit-run, so timestamps/ids don't trip it (keep that
  — a raw `\d{13,19}` match would refuse half your diagnostics).
- **Provider keys are env secrets, NOT vault/user-secret material.** These keys MUST egress to
  authenticate the request, so they live in provider env/config and are never entered through the
  model/agent or stored with the app's user credentials. They're used only in the `Authorization`
  header, never logged or returned. (This is the opposite discipline from a login/credential vault,
  whose secrets must never egress.)
- **Loopback base = no key.** A `localhost`/`127.0.0.1` base URL means a signed-in local proxy
  (e.g. a local Ollama fronting cloud models) that authenticates out-of-band; `isConfigured` treats
  that as usable without a per-request key (`kimi-provider.ts:29-40`). Don't require a key on that
  path.
- **Bound every cloud call.** Each adapter uses an `AbortController` timeout and guards HTTP status +
  empty body; a hung endpoint aborts and falls through instead of stalling the request. Give a large
  overflow model more headroom (45s) than a fast backup (30s). Pair with
  `connector-egress-circuit-breaker` if a tier flaps under load.
- **Never let the ladder act.** It returns `{ok, tier, model, response, escalated, escalationReason}`
  and nothing else. Any send/post/execute stays behind the caller's own confirm + governed path —
  same doctrine as `pluggable-draft-brain`. If you're tempted to auto-run the "obviously fine"
  result, that belongs in a `graduated-autonomy-tiers` gate in the CALLER, never in the router.
- **Order the ladder cheap→dear.** Overflow booster before the secondary backup, both before any
  premium reserve, so the cheapest capable tier that clears the usable bar wins and bulk overflow
  prefers the general booster (`reasoning-router.ts:132-154`).
