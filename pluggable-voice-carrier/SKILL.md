---
name: pluggable-voice-carrier
description: >-
  The swap-the-carrier seam for CLOUD telephony on a Cloudflare Worker: one CarrierAdapter interface
  (issueAgentToken for a browser softphone, placeCall to originate, bridgeToAgent, hangup, start/stopRecording,
  superviseConference for monitor|whisper|barge, verifySignature, parseWebhook -> normalized CallEvent[]) with
  interchangeable Twilio, Telnyx, and mock implementations chosen PER-CAMPAIGN by config (not code). Every
  adapter FAILS CLOSED until its secrets are set, is Workers-safe (Web Crypto + fetch + btoa/atob only, no
  SDK), verifies the provider's webhook signature (Twilio HMAC-SHA1 over URL+sorted-params, Telnyx Ed25519
  over timestamp|body) before trusting an event, and normalizes each provider's call statuses into ONE event
  vocabulary so nothing in the cockpit references a carrier directly. Use WHENEVER a build needs cloud voice
  calling it can re-point later — "add click-to-call / a browser softphone", "originate calls from the app",
  "record calls", "monitor/whisper/barge", "switch from Twilio to Telnyx for cheaper minutes", "don't hard-code
  the phone provider", or "verify the Twilio/Telnyx callback". It COMPLEMENTS hfp-dialer-companion (that is the
  NATIVE no-Twilio SIM dialer; this is the paid-carrier alternative behind the same cockpit), signed-webhook-intake
  (this is the voice-carrier-specific webhook verification layer), predictive-dialer-pacing (decides HOW MANY to
  originate) and local-presence-did-pool (supplies the from-number). Mirrors the processor seam in prepaid-wallet-ledger.
---
# Pluggable Voice Carrier (cloud-telephony adapter seam)

## What it is / when to use / what it composes with
One interface, many carriers — so the calling cockpit is written once and the actual voice provider is a
per-campaign config flip. The reusable win is that **nothing but the adapter file knows the carrier exists**:
originate, record, supervise, and webhook-normalize all go through the seam, so Twilio→Telnyx→Bandwidth is a
config change, not a rewrite. Same shape as the payment-processor seam in `prepaid-wallet-ledger`.

- **Composes with**: `predictive-dialer-pacing` (how many lines to originate), `local-presence-did-pool`
  (the `fromPool` DID passed to `placeCall`), `signed-webhook-intake` (this is the carrier-specific verify layer),
  `hfp-dialer-companion` (the native SIM-dialer alternative to a paid carrier), `append-only-audit-log`.

## Reference implementation (exact source)
- Factory (per-name, test-injectable via `env.__carriers`): `/Users/robbiebrown/Projects/case-plug/src/carriers/index.js` (whole).
- Twilio adapter (AccessToken JWT for the Voice JS SDK softphone, REST originate, Conference monitor/whisper/
  barge, **X-Twilio-Signature HMAC-SHA1** verify, status→event normalize): `src/carriers/twilio.js` (whole);
  token mint `:31-48`, `placeCall` `:74-88`, `superviseConference` `:113-128`, `verifySignature` `:132-140`,
  `parseWebhook` `:142-157`.
- Telnyx adapter (proves the seam — identical interface, **Ed25519** webhook verify, call-control):
  `src/carriers/telnyx.js` (whole); `placeCall` `:34-41`, `verifySignature` `:57-65`, `parseWebhook` `:67-85`.
- Mock adapter (fully test-exercised): `src/carriers/mock.js`.
- Cockpit usage (never touches a carrier directly — always via `getCarrier`): `src/calls.js` — token `:63-69`,
  dial `:71-98`, supervise `:179-189`, carrier webhook → `call_events` `:111-126`.
- Schema: `calls`, `call_events`, `campaigns.carrier` `schema.sql:222-242`.

## How to reapply
1. **Define the interface** exactly: `issueAgentToken(agentId)`, `placeCall({to, fromPool, campaignId, amd})`,
   `bridgeToAgent`, `hangup`, `startRecording`/`stopRecording`, `superviseConference(callRef, mode, supervisorId)`,
   `verifySignature(...)`, `parseWebhook(payload) -> CallEvent[]`. Each returns `{ok:true,...}` or `{ok:false,error}`.
2. **Normalize to ONE event vocabulary** in `parseWebhook` (`queued|ringing|answered|machine|completed|
   no_answer|failed`), so the DB `calls.status` CHECK and the pacer's rollup are carrier-independent.
3. **Fail closed**: read the ready-ness of secrets at construction (`restReady`, `tokenReady`); every method
   returns `{ok:false,'<carrier>_not_configured', method}` until wired. No dev fallbacks.
4. **Pick per campaign**: `getCarrier(campaign?.carrier || env.DEFAULT_CARRIER || 'mock', env)`; store the carrier
   on the `campaigns` row. Tests inject `env.__carriers = { mock: fake }`.
5. **Record media to R2**: `startRecording` returns a deterministic `recording_r2_key` (mirrors the call ref);
   a recording webhook copies the media there.
6. **Softphone**: `issueAgentToken` mints the browser SDK login (Twilio = HS256 JWT with a VoiceGrant; Telnyx =
   telephony-credential token). The page logs in with that token; outbound dial logic lives in the carrier's app.

## Gotchas (from the code)
- **CRITICAL — the webhook handler does NOT call `verifySignature` yet.** `calls.js:111-126` trusts the posted
  events with only a `// PROD: verify the carrier's HMAC signature here` comment; the `verifySignature` methods
  exist in each adapter but are unwired. **Binding to add before production**: in `/webhooks/carrier`, read the
  raw body + the signature header (`X-Twilio-Signature`, or Telnyx `Telnyx-Signature-Ed25519` + `Telnyx-Timestamp`),
  call `carrier.verifySignature(...)`, and return 401 on failure BEFORE `parseWebhook`. Until then any actor who
  knows the URL can forge call events.
- **Twilio's signature is HMAC-SHA1 over the full URL + alphabetically-sorted POST params concatenated** — not
  the JSON body. Sort keys, concat `k+v`, prepend the URL, base64. Telnyx is **Ed25519 over `timestamp|rawBody`**
  and needs the raw (unparsed) body.
- **Ed25519 may be unavailable in the runtime** — the Telnyx verify catches and returns `false` (fail closed),
  never "unverified = trusted".
- **`amd` (answering-machine detection) is a per-call flag** the pacer/queue depend on to label `machine` — pass
  it through; the normalized `answered_by:'machine'` drives disposition + abandonment stats.
- **`fromPool` is a JSON array string** (local-presence DIDs); the adapter parses it and takes `[0]`, else falls
  back to the carrier's default caller ID. A malformed pool must not throw — keep the default.
- **Supervise conventions differ per carrier** (Twilio Conference `Coaching`/`Muted` params vs Telnyx bridge
  `whisper` flag) — that difference is exactly what the seam hides; keep the three modes (`monitor|whisper|barge`)
  identical at the interface.
