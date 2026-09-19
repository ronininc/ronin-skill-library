---
name: outbound-compliance-gate
description: >-
  The fail-closed TCPA/CAN-SPAM eligibility kernel every US outbound product legally needs,
  enforced SERVER-SIDE across voice + SMS + email: a consent-basis predicate, one shared DNC
  suppression list, a per-day attempt cap, area-code→timezone calling-hours (08:00–21:00
  called-party local), a mandatory "Reply STOP" on every text, and a token-gated one-click
  unsubscribe with a CAN-SPAM footer on every email. Use WHENEVER a build will call, text, or
  mass-email contacts/leads/customers — "add a dialer", "SMS campaign", "email blast",
  "outreach", "cold outreach", "drip", "can we text our customers", "is this TCPA/CAN-SPAM
  compliant" — as the ONE place consent/DNC/hours/opt-out policy is defined, before wiring any
  channel. This is the shared dependency of governed-email-outreach, text-campaign-platform,
  and any power-dialer. Guardrails: gates fail CLOSED (a contact is contactable only if it
  passes every check); ONE dnc table and ONE consent predicate govern all channels; never
  predictive/robo/ringless dialing; STOP suppresses across channels instantly; opt-out is
  honored forever across every audience. Extends crm-build-standard's contact/lead model.
---

# outbound-compliance-gate — fail-closed TCPA/CAN-SPAM kernel (voice + SMS + email)

## What it is / when to use
A small set of near-pure functions + one query that decide whether a given contact may be
dialed, texted, or emailed *right now*. Define the policy once; every channel calls it. It
FAILS CLOSED — silence means "do not contact." Drop it in before wiring any voice dialer,
SMS campaign, or bulk email. It is the safe-to-resell kernel behind every Ronin outreach
feature; the other outreach skills (`governed-email-outreach`, `text-campaign-platform`)
depend on the helpers defined here.

Legal footing it implements (not legal advice — it encodes the mechanics regulators expect):
consent basis before contact, a suppression/DNC list honored instantly, per-day frequency
cap, calling-hours in the *called party's* local time, one-tap opt-out on every message, and
an append-only trail. It does NOT replace counsel, a registered exemption, or a KYC/AML vendor.

## Reference implementation (Wavelygth — patterns only, no client data)
All in `worker/index.js` unless noted; open and confirm before lifting.

- **Calling-hours + area-code→TZ resolver** — `worker/index.js` L2371–2399:
  `normalizePhone` (L2371, digits-only, strips a leading US `1`), `AREA_TZ` offset table +
  `AREA_CODE` prefix map (L2373–2380), `withinCallingHours(phone, nowMs)` (L2383–2399). Pure,
  zero-dep, DST-approximated by a blanket +1 over Mar–Nov; **unknown area code falls back to a
  window safe across BOTH ET and PT** (never guesses permissive). Exported for unit testing at
  L3266 (`export { withinCallingHours, normalizePhone }`).
- **Consent predicate** — `leadConsented(r)` L2402: true if the row carries an explicit
  `consent_basis`, OR its `source` is in `DIAL_CONSENTED_SOURCES` (`web/jv/meta/opt_in/opt-in`
  — hand-raisers). `DIAL_ATTEMPT_CAP = 5` L2366.
- **Shared DNC set** — `dncSet(env)` L2403–2406: loads the whole `dnc` table into a
  normalized-phone `Set`. ONE table, all channels.
- **Voice dial-time gate (the fail-closed pattern)** — serve-next at L2463–2472:
  SQL pre-filters `do_not_call = 0 AND call_attempts < DIAL_ATTEMPT_CAP`; JS then rejects any
  row failing `leadConsented(r)` or present in the DNC set; `withinCallingHours` is checked
  per lead at dial time. Disposition at L2510–2520 increments `call_attempts` and flips
  `do_not_call = 1` at the cap or on a `dnc`/`bad_number`/`not_interested` outcome.
- **SMS STOP intake** — `handleTextInbound` L1237–1253: a `^(stop|unsubscribe|quit|end|
  cancel|stopall)` reply does `INSERT OR IGNORE INTO dnc … 'sms_stop'` and skips that number's
  queued/sending rows. `renderText` (L1137–1145) appends "Reply STOP to opt out." to every
  message that doesn't already contain "stop".
- **Email opt-out + CAN-SPAM footer** — `unsubToken`/`unsubLinkFor`/`handleUnsubscribe`
  L1815–1826 (token = `sha256hex(lower(email)+salt)`, idempotent `INSERT OR IGNORE INTO
  email_optout`, token-gated so it isn't an enumeration endpoint); the always-on unsubscribe
  footer is baked into `renderEmailBody` L1786–1793.
- **Schema** — `worker/migrations/0009_dialer.sql` (the `dnc` table + `consent_basis`,
  `call_attempts`, `do_not_call` columns on the contact table + the append-only `calls` log),
  `0013_email_optout.sql` (`email_optout`), `0012_compliance.sql` (append-only event log
  pattern for regulated determinations).
- **Proofs** — `worker/lib/_proof/dialer.test.mjs` (consent/DNC/cap/hours all fail closed),
  `text-campaign.test.mjs` (STOP suppresses + consent-gated enqueue), `mass-email.test.mjs`
  (opt-out honored, unsubscribe token). The calling-hours resolver is also unit-tested pure.

## How to reapply it
1. **Schema.** Add to your contact/lead table: `consent_basis TEXT`, `call_attempts INTEGER
   NOT NULL DEFAULT 0`, `do_not_call INTEGER NOT NULL DEFAULT 0`. Create the shared
   `dnc (phone PRIMARY KEY, reason, added_by, added_at)` and, if you email,
   `email_optout (email PRIMARY KEY, reason, at)`. Store phones as normalized digits.
2. **Lift the pure helpers** verbatim: `normalizePhone`, `AREA_TZ`, `AREA_CODE`,
   `withinCallingHours`, `leadConsented`, `DIAL_CONSENTED_SOURCES`, `dncSet`. No edits needed
   except your consented-source names and cap constant.
3. **Gate every channel with the same three checks, in this order, fail-closed:**
   `leadConsented(row)` AND NOT `dncSet` contains the phone/`email_optout` contains the email
   AND under the per-day cap AND (voice/SMS) `withinCallingHours(phone, Date.now()).ok`. If any
   is false, SKIP and record why — never contact "just this once."
4. **Wire opt-out intake on every channel:** SMS/voice inbound STOP → `INSERT OR IGNORE INTO
   dnc`; email → the token-gated `/api/unsubscribe` + the `renderEmailBody` footer. Suppression
   must take effect on the very next pass (it does, because every pass re-reads the set).
5. **Log it.** Append-only `calls`/campaign-recipient rows so you can show who was contacted,
   when, and the outcome — regulators (and disputes) require the trail.
6. **UI (optional):** a one-click "Add to DNC" control mid-interaction and a DNC/opt-out
   count on the ops console.

## Gotchas (from the code + comments)
- **Unknown area code must fail toward restriction, not permission.** The resolver requires
  8–21 in *both* ET and PT for unknown codes (effectively 11:00–21:00 ET) — copy that, don't
  default to a single permissive zone.
- **DST is approximated** (blanket +1 over Mar–Nov). It's deliberately conservative; if you
  need exact local time, swap in a real TZ library but keep the fail-closed fallback.
- **Normalize before every comparison.** DNC lookups, dedup, and inbound `from` matching all
  run through `normalizePhone`; a raw `(602) 555-0101` vs `6025550101` will silently miss the
  DNC list otherwise. The proof seeds mixed formats precisely to catch this.
- **ONE dnc + ONE consent predicate for all channels.** A STOP text must stop future *calls*
  too. Don't fork per-channel suppression lists.
- **The consent basis is the row's, not the campaign's.** `source='opt_in'` counts as consent;
  a NULL `consent_basis` on a non-opt-in source means "do not contact," not "contact once."
- **Opt-out is forever and cross-audience.** `email_optout`/`dnc` are excluded by *every*
  audience builder, permanently — never "expire" an opt-out.
- **Unsubscribe endpoint is token-gated** (`sha256hex(email+salt)`) so it can't be walked to
  enumerate or mass-suppress addresses; it's still idempotent and needs no session.
- **Never predictive/robo/ringless/caller-ID-spoofing.** This kernel governs *human-initiated*
  contact only; automated dialing is a different (and far riskier) legal regime.
