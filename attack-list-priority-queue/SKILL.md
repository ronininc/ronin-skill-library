---
name: attack-list-priority-queue
description: >-
  A computed-on-read daily work queue for a CRM that ranks the leads worth calling right now by
  URGENCY × POTENTIAL GAIN and buckets them first-thing / last-thing / follow-ups — with a per-row
  priority fill bar — and adds NO new tables (everything is derived from existing appointments,
  deals, and reply data at request time). Urgency comes from the soonest upcoming appointment
  (overdue = max, decaying over a tunable window) or an unread reply; gain from the best booked deal
  value, else a capacity-signal × target-deal-size estimate, else a configured baseline (flagged
  "estimated"). Use WHENEVER a CRM needs a "call list", "who do I work today", "attack list",
  "prioritized follow-up queue", "morning/EOD list", "rank my leads by urgency and value", or "what
  should I do first" — a ranking VIEW, not a stored queue. This is prioritization ONLY: it
  COMPLEMENTS d1-work-queue (the atomic claim-once dequeue — use THAT when multiple seats work the
  list and each row must go to exactly one worker; this decides ORDER, that assigns OWNERSHIP) and
  hfp-dialer-companion / crm-build-standard's power-dialer (the thing that actually places the call).
  Do NOT rebuild the claim lock or the dialer here. Guardrails: it recomputes every read (always
  fresh, but cap the query LIMITs), the "gain" baseline is business-specific (parameterize it), and
  an estimated value is always marked so nobody mistakes it for a booked number.
---

# Attack-List Priority Queue

## What it is / when to use
A read-time ranking of the leads most worth working, blended from signals the CRM already has. It
answers "what should I do first?" and lays the day out as first-thing / last-thing / follow-ups.
Reach for it whenever an operator or rep needs a prioritized daily list off live CRM data with no
extra bookkeeping.

**Composes with:** `d1-work-queue` (when several seats work the same list, rank with THIS then claim
each row atomically with THAT — ranking decides order, the claim decides ownership);
`hfp-dialer-companion` and the power-dialer in `crm-build-standard` (they place the calls — this
just orders them); `pipeline-autopilot` / `reply-intent-triage` (they generate the appointments and
replies this queue reads). It owns none of those — it is a pure derived view.

## Reference implementation (ronininc CRM — OPEN before lifting)
Cloudflare Worker + D1, `worker/priorities.ts` L1-192 — one read handler, no migration:
- **Tunables** L24-26 — `DEFAULT_GAIN_CENTS` (baseline estimate when nothing else is known) and
  `URGENCY_WINDOW_DAYS` (14 — appointments beyond it decay to 0 urgency).
- **Inputs (4 parallel reads)** L60-103 — open/pending appointments joined to contacts (L60-66); best
  booked deal value per contact (`MAX(value_cents)`, L69-73); a lead-gen capacity/need signal + the
  run's target deal size per contact (L76-88); latest reply per contact with unread count + snippet
  (L91-103).
- **Free-text appointment parsing** `parseApptAt` L32-45 — parses the scheduler's own emitted format
  ("Tue, Sep 15, 2026 · 9:00 AM (America/Phoenix)"), strips tz/separators, `Date.parse`; returns
  null for freeform ("Weekday mornings") → those become `anytime`. `slotFor` L48-52 buckets am/pm.
- **Gain ladder** `gainFor` L114-123 — booked deal (`estimated:false`) → `capacity × target`
  (`estimated:true`) → `DEFAULT_GAIN_CENTS` (`estimated:true`).
- **Row assembly + dedupe** `ensure` L125-141 + L143-170 — one row per contact, keep the soonest
  future appointment; also fold in reply-only contacts (replied but no appointment).
- **Scoring** L172-189 — urgency: overdue-but-open = 1, else `clamp01(1 − (appt − now)/window)`,
  reply-only base (0.72 unread / 0.45 read / 0.25 none); gain normalized against the max in the set;
  `priority = 0.55·urgency + 0.45·gain`; sort desc, return top 60 (L191).
- **Route** `worker/admin.ts` L282 — `GET attack-list` behind the admin gate.
- **UI** `public/admin/admin.js` L749-794 — buckets the rows (overdue/am = "First thing", pm = "Last
  thing", anytime = "Follow-ups"), draws a `.ax-pri-fill` bar at `priority × 100%`, tags overdue /
  unread-reply, click-through to the contact.

## How to reapply it
1. **No migration.** This derives from tables the CRM already has (appointments, deals, replies, and
   whatever capacity/fit signal you carry). Nothing to add.
2. **One read handler.** Do the parallel reads → build one row per contact (dedupe, keep soonest
   future appointment, include reply-only contacts) → compute urgency + gain → normalize gain
   against the set max → blend `priority` → sort → slice top-N.
3. **Parameterize the constants.** Replace the gain baseline with the client's real average deal
   size and set the urgency window to their sales cadence. Adjust the `0.55/0.45` weights to taste.
4. **Route.** Expose it as a single `GET` behind the admin/staff gate. No writes, so it needs no
   CSRF/same-origin beyond the gate.
5. **UI.** Render the three buckets + the fill bar; tag overdue and unread-reply; click a row to open
   the contact. Recompute on load (and on a manual refresh) — there's no stored state to invalidate.

## Gotchas
- **Computed on read = always fresh, but O(contacts) per request.** Keep the source's LIMIT caps
  (appointments 500, output top-60) or a big CRM turns this into a slow, memory-hungry query. If the
  list gets huge, cache it briefly or precompute on cron — but then you've traded away freshness.
- **Appointment time is parsed from free text.** It handles the SCHEDULER'S OWN format; anything
  freeform returns null and the row falls to `anytime`. If your scheduler emits a different string,
  update `parseApptAt` or you'll silently bucket real appointments as "no set time."
- **Gain is a fallback ladder and estimates are flagged.** Never show an estimated value without the
  `~ est.` marker — an operator must not mistake a `capacity × target` guess for a booked deal.
- **The baseline gain constant is business-specific.** The reference uses a merchant-site baseline;
  hardcoding it into a different client silently mis-ranks every un-dealt lead. Parameterize it.
- **This ranks; it does not lock.** Two reps hitting the same list see the same order — nothing stops
  them both calling the top row. Add `d1-work-queue` for claim-once when more than one seat works it.
- **Gain is normalized against the CURRENT set's max**, so priorities are relative within today's
  list, not absolute across time — fine for a daily list, but don't persist the score as if it were.
