---
name: dormant-reactivation
description: >-
  A win-back engine for a Cloudflare Worker + D1 CRM: once a day, at a configured
  local hour, it finds contacts with no activity in N days — honoring the
  suppression list and skipping anyone already in the reactivation queue — drafts
  a personalized win-back email per contact into a review queue, and (on operator
  approval) enrolls each draft into a governed reactivation campaign with a
  per-recipient unsubscribe token. Use WHENEVER a CRM should "re-engage cold
  leads", "win back dormant customers", "email people who went quiet", "find
  stale contacts and follow up", "reactivation campaign", or "nudge no-activity
  leads." It COMPLEMENTS crm-build-standard (the contacts/activities spine it
  reads) and, critically, governed-email-outreach + text-campaign-platform +
  outbound-compliance-gate: this skill only DETECTS dormancy and DRAFTS/QUEUES —
  it hands actual sending, throttling, suppression enforcement and unsubscribe
  handling to those skills' campaign rail; do NOT re-implement the sender or the
  suppression list here. Guardrails: drafts are never auto-sent (human queues
  each, or a draft-tier autopilot does) — it only prepares; it respects
  suppressions at BOTH detect and queue time; it runs at most once per local day
  via a claim; and it never re-queues a contact already draft/queued/sent.
---
# dormant-reactivation — detect the quiet, draft the win-back

## What it is / when to use
The "who went cold, and what do we say to them" half of retention. A daily job
computes each contact's last-touch (most recent activity, else the contact's own
`updated_at`), selects those past the dormancy cutoff who aren't suppressed and
aren't already queued, and writes one personalized draft per contact into a
`reactivation_queue` the operator reviews. Approving a draft enrolls it into the
existing governed email campaign — so the actual send rides the same throttle,
suppression and unsubscribe machinery every other campaign uses. Use it on any
CRM with a contact/activity history that wants to recover dormant relationships.

**Composes with (do not duplicate):**
- **crm-build-standard** — supplies `contacts`, `activities`, `companies`.
- **governed-email-outreach / text-campaign-platform** — own the actual send,
  the rate limit, and the reply-stops-it behavior. This skill enqueues into
  their campaign; it does not send.
- **outbound-compliance-gate** — the suppression list this skill checks (twice)
  and the unsubscribe tokens it attaches.
- **graduated-autonomy-tiers / pipeline-autopilot** — the reference ships this as
  an operator-approved (draft) flow; wire a `winbacks` tier if you want a
  draft/auto dial (money-never-auto doesn't apply — it's a message).

## Reference implementation (ronininc — patterns only, no client data)
- `worker/business-apps.ts`
  - **L381–405** `buildReactivationDrafts(env, limit)` — the detector + drafter. The dormancy query: `LEFT JOIN activities`, `GROUP BY c.id HAVING COALESCE(MAX(a.created_at), c.updated_at) <= cutoff`, `LEFT JOIN outreach_suppressions ... WHERE s.email IS NULL` (skip suppressed), `AND NOT EXISTS (SELECT 1 FROM reactivation_queue q WHERE q.contact_id=c.id AND q.status IN ('draft','queued','sent'))` (skip already-in-flight), excludes `%@no-email.local` placeholders, ordered oldest-first. Drafts a per-contact subject/body (encrypted at rest) and `INSERT OR IGNORE` into the queue; counts real inserts via `meta.changes`.
  - **L419–449** `queueReactivation(req, env, me)` — operator approves one draft: ensures the reactivation campaign row exists, **re-checks suppression at queue time** (if now suppressed → mark the draft `suppressed`, refuse), then in a `DB.batch` inserts a `campaign_recipients` row (status `queued`, a `randomHex(24)` unsubscribe token) and flips the draft to `queued`.
  - **L474–489** `localDayHour(tz)` + `runBusinessAutomations(env)` — the once-daily cron gate: returns unless `reactivation_enabled`, and unless the current local hour equals `reactivation_hour` AND `last_reactivation_day` isn't already today; builds drafts, then stamps `last_reactivation_day` so it runs at most once per local day.
- `migrations/0012_business_apps.sql`
  - **L3–15** `business_settings` — `dormant_days` (CHECK 7..730), `reactivation_enabled`, `reactivation_hour` (0..23), `last_reactivation_day`.
  - **L118–133** `reactivation_queue` — `status` (`draft|queued|sent|suppressed|dismissed`), `draft_subject`, `draft_body`, `campaign_id`, and the key guard **`UNIQUE(contact_id, status)`** + status index.
- `worker/admin.ts` **L366–368** — routes: `GET business/reactivation` (list), `POST business/reactivation/build` (run detector now), `POST business/reactivation/queue` (approve one).
- `worker/index.ts` **L189** — `runBusinessAutomations(env)` inside the existing `scheduled()` `Promise.all`.
- `public/admin/admin.js` **L547–559** — the review UI: "Find dormant leads" button, draft cards, per-draft "Queue campaign".

## How to reapply it
**1. Schema.** Add dormancy settings to your single-row settings table (`dormant_days`, `reactivation_enabled`, `reactivation_hour`, `last_reactivation_day`) and a queue:
```sql
CREATE TABLE IF NOT EXISTS reactivation_queue (
  id TEXT PRIMARY KEY, contact_id TEXT NOT NULL REFERENCES contacts(id),
  reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',   -- draft|queued|sent|suppressed|dismissed
  draft_subject TEXT NOT NULL, draft_body TEXT NOT NULL, campaign_id TEXT,
  queued_at INTEGER, sent_at INTEGER,
  created_at INTEGER NOT NULL DEFAULT (unixepoch()), updated_at INTEGER NOT NULL DEFAULT (unixepoch()),
  UNIQUE(contact_id, status)
);
```

**2. Detector.** One query that (a) computes last-touch via `COALESCE(MAX(activity.created_at), contact.updated_at)`, (b) `HAVING last_touch <= now() - dormant_days*86400`, (c) LEFT-JOINs the suppression list and keeps only `WHERE suppression IS NULL`, (d) `NOT EXISTS` the in-flight queue statuses, (e) drops placeholder emails, ordered oldest-first, `LIMIT` bounded. Draft a personalized subject/body per row (name + company), encrypt if you store bodies encrypted, `INSERT OR IGNORE`, count `meta.changes`.

**3. Approve → enqueue.** On operator approval: re-check suppression (state may have changed since the draft), then batch-insert a `campaign_recipients` row (status `queued`, a random unsubscribe token) into your governed campaign and flip the draft to `queued`. The campaign rail sends it, honoring its own throttle + reply-stop.

**4. Daily cron gate.** In your existing `scheduled()` task, compute the operator's local day+hour (`Intl.DateTimeFormat` in the CRM timezone), bail unless `enabled && local.hour===reactivation_hour && last_reactivation_day!==local.day`, build drafts, then persist `last_reactivation_day=local.day`.

**5. Routes + UI.** List drafts, a "find dormant now" button (calls the detector), and per-draft "Queue campaign". Show that drafts honor suppressions and that queueing routes through the governed campaign.

## Gotchas
- **Draft ≠ send.** This engine only *prepares*. Sending is a separate, governed step (operator approval or a draft-tier autopilot). Never auto-blast from the detector — that's how a "win-back" becomes spam.
- **Check suppression twice.** Once in the detector's query, and AGAIN at queue time — a contact can opt out between the nightly draft and the operator's morning approval. The reference marks the draft `suppressed` and refuses on that recheck.
- **`UNIQUE(contact_id, status)` + the `NOT EXISTS` guard prevent nagging.** Together they stop the same dormant contact being drafted/queued repeatedly across nights. Don't drop the uniqueness — it's the idempotency.
- **Once per local day, via a claim, not a guess.** Gate on `local.hour===reactivation_hour && last_reactivation_day!==today` and then write today's date. On a 5-minute cron this fires once; without the day-stamp it re-runs twelve times in the target hour.
- **Last-touch is `MAX(activity) OR contact.updated_at`.** A contact with zero activities still has a last-touch (their creation/update), so brand-new-but-never-touched contacts don't instantly read as dormant on day one — tune `dormant_days` accordingly (floor 7).
- **Exclude placeholder emails.** Rows like `…@no-email.local` must be filtered or the detector drafts unsendable mail.
- **Bound the batch.** Clamp `limit` (reference caps at 250) so one nightly run stays inside the cron CPU budget; the next night catches the rest, oldest-first.
- **Encrypt drafted bodies at rest** if the CRM encrypts other free-text (activities, notes) — the draft holds a personalized message about a real person.
