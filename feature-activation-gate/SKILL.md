---
name: feature-activation-gate
description: >-
  Ship a paid capability DARK and flip it on per-account with EITHER a Worker
  secret OR an operator-saved setting, refusing every call until then with an
  honest, purchase-shaped 402 (never a fake success). This is the monetization
  switch — the literal "anything I can profit off of" lever for a Cloudflare
  Worker + D1 build. Use WHENEVER a feature should be OFF until paid/enabled:
  "add-on", "paywall", "premium feature", "activation", "gate this behind a
  flag", "ship it dark", "flip it on for this account", "sell X as an upgrade",
  "402 / not activated", "trial vs paid", or wrapping any optional module so it
  stays dormant until Ronin (or the operator) turns it on. Backend pattern on a
  Cloudflare Worker + D1; pairs with append-only-audit-log (log every flip) and
  with any gated handler. Guardrails: the SECRET is the real switch (survives a
  DB wipe, the operator can't self-enable a paid tier); the saved setting is the
  operator-flippable convenience — check the secret FIRST. The enabled() read
  fails CLOSED (a DB hiccup leaves the feature OFF, never open). Background/cron
  paths must NOT throw a 402 (no HTTP client to receive it) — they return a
  {skipped:'not_enabled'} marker and log it, so a disabled feature never fakes
  work. Values are strings '1'/'0', compared === '1'.
---
# feature-activation-gate — ship dark, flip on, refuse honestly

## What it is / when to use
A two-source activation switch for a Cloudflare Worker + D1 product. A paid
capability stays dormant until it is enabled by **either** a Worker secret
(`FEATURE_ENABLED=1`) **or** a row in the `app_settings` key/value table. Every
gated handler checks the switch first and, when off, returns a **402 Payment
Required** with copy that reads like a purchase prompt — never a fake 200. Use
it to sell any optional module (outreach, SMS, a connector, an analytics tier)
without branching the codebase: one predicate, one gate line, one honest refusal.

## Reference implementation (Wavelygth — patterns only, no client data)
- `~/Projects/clients/wavelygth/worker/index.js`
  - **L1023–1027** `outreachEnabled(env)` — the canonical secret-OR-setting predicate.
  - **L1031–1032** honest-degrade in a background path (`runDailyCampaign` returns `{ skipped: 'not_enabled' }` / `{ skipped: 'no_email_provider' }` — no 402 from cron).
  - **L1090** the 402 gate + copy in an HTTP handler (`handleOutreachRun`).
  - **L1132–1136** `textEnabled(env)` — a second feature on the identical pattern.
  - **L1262–1272, L1288** `googleConfig(env)` — the *config-presence* variant: returns `null` when creds are absent, and the handler answers `402 "isn't configured on this account yet. Contact Ronin to activate…"`.
  - **L441–446** `readSettings(env)` — the shared settings reader (fails closed via `.catch(() => ({}))`).
- `~/Projects/clients/wavelygth/worker/migrations/0006_profile_branding.sql` **L10–14** — the `app_settings (key, value, updated_at)` table.

## How to reapply it
**1. Schema** — one key/value table (already present if you use the branding/settings pattern):
```sql
CREATE TABLE IF NOT EXISTS app_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT,
  updated_at TEXT NOT NULL
);
```

**2. The predicate** — secret first, then the saved setting. Fails closed:
```js
async function readSettings(env) {
  const { results } = await env.DB.prepare('SELECT key, value FROM app_settings')
    .all().catch(() => ({ results: [] }));            // DB hiccup ⇒ {} ⇒ feature OFF
  const out = {}; for (const r of (results || [])) out[r.key] = r.value; return out;
}
async function featureEnabled(env) {
  if (env.FEATURE_ENABLED === '1') return true;       // the paywall: a Ronin-set secret
  const s = await readSettings(env).catch(() => ({}));
  return s.feature_enabled === '1';                   // operator-flippable convenience
}
```

**3. Gate every HTTP handler** for the feature, up front, with a purchase-shaped 402:
```js
async function handleFeatureRun(req, env, me, url) {
  if (!(await featureEnabled(env)))
    return bad('That feature is not activated on this account. Contact Ronin to enable it.', 402);
  // …do the real work…
}
```

**4. Degrade honestly in automated paths** (cron / webhook) — there is no client to
receive a 402, so return a marker and log it; NEVER perform the work as if enabled:
```js
async function runScheduledJob(env) {
  if (!(await featureEnabled(env))) return { skipped: 'not_enabled' };
  // …
}
```

**5. Config-presence variant** — when "enabled" means "credentials are wired"
(e.g. an OAuth app), let the config resolver return `null` and gate on that:
```js
async function serviceConfig(env) {
  const s = await readSettings(env).catch(() => ({}));
  const id = env.SERVICE_CLIENT_ID || s.service_client_id;
  const secret = env.SERVICE_CLIENT_SECRET || s.service_client_secret;
  if (!id || !secret) return null;                    // not configured ⇒ gate says 402
  return { id, secret /*, endpoints… */ };
}
// handler: const cfg = await serviceConfig(env);
// if (!cfg) return bad("X isn't configured on this account yet. Contact Ronin to activate it.", 402);
```

**6. Flip it on.** Secret path: `npx wrangler secret put FEATURE_ENABLED` → `1`.
Setting path: an admin PUT writes `feature_enabled='1'` into `app_settings`
(`INSERT … ON CONFLICT(key) DO UPDATE SET value=excluded.value`). Log the flip with `audit()`.

## Gotchas
- **402 vs 403.** Use **402 Payment Required** for "not activated / needs
  purchase" — it reads as a purchase prompt and is distinct from 403 (you're
  authed but forbidden). Wavelygth uses 402 for both the feature gate and the
  "not configured" connector gate; router-level scope refusals stay 403.
- **Never fake a 200.** A disabled feature must refuse (402) or skip
  (`{skipped}`); it must never return a success it didn't produce. That honesty
  is the whole product promise.
- **Cron can't receive a 402.** Any `scheduled()`/webhook caller must branch on
  the predicate and return a skip marker — throwing an HTTP status there just
  logs an error and can look like a failure. Log the skip so it's auditable.
- **Check the secret FIRST.** The secret is the true entitlement (an operator
  can't grant themselves a paid tier by writing their own `app_settings`, and it
  survives a DB reset). The saved setting is the convenience toggle layered on top.
- **Fail closed.** `readSettings` catches to `{}` so a transient D1 error leaves
  the feature OFF, never accidentally ON.
- **Values are strings.** `app_settings.value` is TEXT — compare `=== '1'`, and
  store `'1'`/`'0'` (or delete the row to clear), not booleans.
