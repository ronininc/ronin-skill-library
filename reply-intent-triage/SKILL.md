---
name: reply-intent-triage
description: >-
  A dependency-free, LLM-free heuristic classifier that reads an inbound reply
  (subject + snippet, decrypted at rest) and labels it interested |
  not_interested | question | auto | unknown, then ROUTES it — opt-outs are
  auto-added to the suppression list and their queued sends cancelled, interested
  replies advance toward booking, auto-replies/bounces are skipped — with zero
  external or model calls so it runs free on every cron tick. Use WHENEVER a CRM
  must "sort inbound replies", "detect who's interested", "auto-handle
  unsubscribes/opt-outs", "classify email replies", "route replies without an
  LLM", or "figure out what a reply means" at scale and near-zero cost. It is the
  CLASSIFIER + reply-routing atom that pipeline-autopilot calls each tick (do NOT
  fold the cron orchestration or the booking send into this skill — those are
  pipeline-autopilot and self-schedule-booking). It COMPLEMENTS
  governed-email-outreach and outbound-compliance-gate: this is where a reply
  READ as an opt-out becomes a suppression entry, closing the compliance loop
  those skills open. Guardrail: it's a first-pass heuristic, not certainty —
  opt-out and auto-reply are treated as safe-to-act (suppress / skip), while
  interested/question/unknown only STAGE work a human or a higher tier confirms;
  never auto-send anything irreversible off a raw classification.
---
# reply-intent-triage — free heuristic reply classifier + router

## What it is / when to use
Two small, pure pieces: (1) `classifyIntent(text)` — an ordered set of
case-insensitive regexes that map a reply's subject+snippet to one of five
labels, and (2) `triageReplies(env)` — the routine that pulls untriaged replies,
classifies them, writes the label + a handling state, and takes the *safe*
automatic actions (suppress opt-outs, skip machine replies) while merely
*staging* the rest. It costs nothing per run (no API, no model), so it can run on
every cron tick over every new reply. Use it as the intake brain for any CRM
that gets email replies at volume.

**Composes with (do not duplicate):**
- **pipeline-autopilot** — the cron orchestrator that *calls* `triageReplies`
  each tick and then acts on `interested` rows. This skill is only the classify
  + route step; it does not own the schedule or the booking send.
- **self-schedule-booking** — what `interested` eventually flows into.
- **governed-email-outreach / outbound-compliance-gate** — this skill writes the
  suppression rows those skills read before sending, closing the opt-out loop.

## Reference implementation (ronininc — patterns only, no client data)
- `worker/autopilot.ts`
  - **L113–121** `classifyIntent(text)` — the whole classifier. Order matters:
    empty → `unknown`; **auto/bounce first** (out-of-office, auto-reply, mailer-
    daemon, undeliverable); then **opt-out** (unsubscribe, not interested, remove
    me, stop emailing, "we're all set", "already have"); then **interested**
    (interested, let's talk/meet, call me, book, schedule, pricing/quote, "how
    much", "send info", bare "yes"); then `?` → `question`; else `unknown`.
  - **L381–405** `triageReplies(env)` — the router: selects `WHERE autopilot_state IS NULL LIMIT 25`, **decrypts** subject+snippet (`decField`), classifies, then:
    - maps intent → state: `not_interested → 'handled'`, `auto → 'skipped'`, else `'pending'`;
    - writes `intent`, `autopilot_state`, `handled_at`;
    - on `not_interested`: `INSERT OR IGNORE` into `outreach_suppressions` (reason `reply-optout`) **and** `UPDATE campaign_recipients SET status='suppressed'` for still-live sends to that address, in a `DB.batch`;
    - logs a heartbeat action either way (`suppressed` or `intent_<label>`).
- `migrations/0020_autopilot.sql` **L45–48** — the `campaign_replies` ALTERs the router writes: `intent`, `autopilot_state` (`pending|handled|skipped`), `handled_at`.

## How to reapply it
**1. Schema.** On your inbound-reply table add `intent TEXT`, `autopilot_state TEXT` (`pending|handled|skipped`), `handled_at INTEGER`. You also need a `suppressions(email, reason, created_at)` table (from your outreach skill) and a recipients table with a `status` you can flip to `suppressed`.

**2. The classifier — copy the shape, tune the words.** Keep the ordering; it's the correctness. A dependency-free version:
```ts
export function classifyIntent(text: string): 'interested'|'not_interested'|'question'|'auto'|'unknown' {
  const t = (text || '').toLowerCase();
  if (!t.trim()) return 'unknown';
  if (/\b(out of office|automatic reply|auto-?reply|vacation responder|undeliverable|mailer-daemon|delivery status notification)\b/.test(t)) return 'auto';
  if (/\b(unsubscribe|not interested|no thanks|remove me|take me off|stop emailing|do not contact|not a good fit|we're all set|already have)\b/.test(t)) return 'not_interested';
  if (/\b(interested|let'?s (talk|chat|meet|connect)|sounds good|tell me more|call me|book|schedule|available|pricing|price|quote|how much|send (me )?(more|info|details)|yes\b)\b/.test(t)) return 'interested';
  if (t.includes('?')) return 'question';
  return 'unknown';
}
```
Verticalize the vocab per client (a restaurant's "interested" words differ from an agency's), but keep auto/bounce and opt-out ahead of interested.

**3. The router.** Pull a bounded batch of untriaged replies, decrypt the text if you store it encrypted, classify, set state, and take **only the safe** automatic actions in a single `DB.batch`: suppress opt-outs and cancel their queued sends. Everything else is `pending` for a human or a higher autonomy tier. Log one audit row per reply.

**4. Wire it.** Call `triageReplies(env)` from your autopilot/cron tick (pipeline-autopilot), gated by that feature's enable + a `reply_triage` tier of `auto`.

## Gotchas
- **Order is the logic.** Classify auto-replies and opt-outs BEFORE "interested" — an out-of-office that says "I'll get back to you, sounds good" must not read as interested, and "not interested, please unsubscribe" must not match the `interested` list. Test the ambiguous overlaps.
- **Opt-out is the only send-affecting auto-action, and it's the safe direction.** Suppressing is fail-safe (you stop mailing someone). Never auto-*send* off a raw `interested` — that only stages a booking a tier/human confirms.
- **Decrypt at read.** If subjects/snippets are encrypted at rest (they should be), decrypt inside the router before matching; matching ciphertext silently yields all `unknown`.
- **State, not just label.** Persisting `autopilot_state` is what stops re-processing every tick — select `WHERE autopilot_state IS NULL`. Without it the classifier re-runs on the whole table forever.
- **Suppress by the actual From address.** Opt-outs key on `from_email` lowercased; also cancel that address's `queued|sending|sent` recipients so an in-flight campaign stops immediately.
- **`unknown`/`question` are not failures.** They're "a human should look" — surface them, don't discard. The heuristic is a triage nurse, not a diagnosis.
- **It's advisory.** This is a cheap first pass; a wrong `interested` costs one extra email, a wrong `not_interested` wrongly suppresses — so keep the opt-out list conservative and easy for the operator to review/undo.
