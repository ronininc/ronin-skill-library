# In-CRM power dialer (optional, governed outreach)

A live-agent power dialer that lives inside the CRM: the agent hits Start, it auto-dials the next
eligible contact from a list, detects call progress (ringing → busy → voicemail → **human**), skips
everything that isn't a person, and on pickup bridges the call to the agent's browser softphone and
screen-pops the contact + disposition buttons. **Progressive/power dialer with a human in the loop —
never predictive, never a robodialer, never caller-ID spoofing.** Saves dialing time; the human talks.

## Compliance gates (build FIRST, fail closed) — non-negotiable
1. **Lawful basis per contact** — dial only where `consent_basis` is set; surface it on the card.
2. **DNC suppression** — scrub every number against an internal `dnc` table before dialing; honor
   opt-outs instantly (a one-click DNC button that ends the call).
3. **Calling hours** — no dial before 08:00 / after 21:00 in the *called party's* local time (derive
   from area code; allow override).
4. **Frequency caps** — per-contact attempts/day + rolling window, counted in the DB.
5. **Registered caller ID + STIR/SHAKEN** — the client's own verified number; no spoofing.
6. **Recording consent** — off by default; if on, respect one-party vs all-party by the called
   party's state, with a disclosure + stored consent.
7. **Append-only audit** — every dial (contact, agent, caller-id, times, outcome, disposition,
   consent basis) → the CRM's `activities`/audit log. Never mutated.

Out of scope without a separate compliance pass: predictive/auto-blast dialing, prerecorded/AI-voice
or ringless-voicemail drops, any caller-ID spoofing.

## Architecture (composes the CRM guts)
- **Telephony:** Twilio Programmable Voice (client brings their own account + verified number); the
  agent's phone is the **Twilio Voice JS SDK softphone** in the browser. Telnyx is an equivalent alt.
- **Call progress:** Twilio Answering Machine Detection — only `human` bridges; voicemail/busy/no-answer
  auto-advance. Expose a manual "not a person → next" too.
- **Worker endpoints** (`cf-functions`, auth-gated via `cf-identity`, role agent/admin): `/token`
  (Voice SDK JWT), `/session/start|end`, `/next` (returns the next **eligible** contact — DNC +
  hours + cap + consent filters applied **in SQL**, and locks it so two agents can't grab it),
  `/twiml/outbound` (`<Dial>` from the caller-id with `machineDetection`), `/status` (Twilio webhook →
  writes the outcome `activity`, idempotent on CallSid), `/disposition` (outcome + note + callback →
  advances), `/dnc` (suppress instantly, mid-call callable).
- **Data:** reuses `contacts` (+ `phone`, `consent_basis`, `status='dnc'`), `activities` (each dial),
  a `dnc` table, and `call_sessions`. Recordings (if on) → **R2**, pointer in `media_objects`.
- **Scale:** `activities` is append-heavy → it shards by the contact root via `commerce-spine`'s
  router; recordings sit in R2 (free 10 GB). Dialing leans on scoring to order the list (call the
  highest-propensity contacts first — `references/intelligence/score.mjs`).

## Free-tier note
The dialer's CF cost is just Worker requests + D1 writes (well within free for one agent). The real
cost is the telephony account (Twilio per-minute) — that's the client's, not Cloudflare's.

## Build gate
Prove the compliance gates with a local test BEFORE any telephony (DNC number skipped, 22:00-local
skipped, capped/ no-basis skipped), then wire Twilio behind a flag with test credentials, verify one
call to your own phone (human bridges, voicemail auto-advances), and only then go live — operator
approves, and never dial real consumers without their go-ahead. A full paste-ready build brief for a
fresh session lives alongside this as the dialer boot prompt.
