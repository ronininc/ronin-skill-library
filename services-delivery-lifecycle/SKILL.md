---
name: services-delivery-lifecycle
description: >-
  The post-deal delivery back-office for an agency/contractor/services CRM on Cloudflare Worker + D1:
  proposals (deposit% + optional monthly retainer + encrypted scope) → an idempotent "on payment"
  hook that auto-activates onboarding (creates a project, best-effort Google Drive client folder, seeds
  a default kickoff-task checklist, and flips proposal→paid + contact→customer in one batch) → a
  project board (onboarding | active | blocked | completed) with per-task todo/doing/done → and, the
  moment a project is marked completed, auto-proposes a recurring retainer AND opens a referral/review
  request. Use WHENEVER a services CRM needs the half AFTER the deal closes: "proposals", "scope +
  deposit", "onboard the client", "kickoff checklist", "project/delivery board", "retainer after
  delivery", "ask for a referral/review when done", "what happens once they pay". It COMPLEMENTS
  crm-build-standard (the contacts/deals/activities core it sits on — do NOT rebuild those),
  google-oauth-connector (the Drive/Calendar auth it calls — do NOT re-implement OAuth), and
  wire-payment-collect-reconcile (the settlement event that FIRES the onboarding hook — this skill
  exposes `activateOnboarding`, that skill calls it). Also pairs with fail-closed-onboarding-gate when
  activation must wait on vetting rather than just payment. Guardrails: onboarding is idempotent (one
  project per proposal); the completion-side retainer is only PROPOSED, never auto-billed (money never
  auto); free-text scope/notes are AES-GCM encrypted at rest.
---

# services-delivery-lifecycle — proposal → onboarding → delivery → retainer + referral

## What it is / when to use
Everything that happens after "yes": you draft a proposal (fixed value, deposit %, optional retainer,
encrypted scope); when payment is confirmed the system opens onboarding automatically — a project, a
client Drive folder, a five-step kickoff checklist, and status flips on the proposal and the contact;
you run the work on a small kanban; and on completion the CRM immediately teed up next revenue (a
proposed retainer) and the growth loop (a referral/review request). It is the delivery organ that
crm-build-standard deliberately stops short of. Reach for it for any service business —
agency, contractor, consultancy, studio — that sells scoped engagements and wants the money-to-delivery
handoff to be one governed flow instead of scattered manual steps.

**Composes with (do not duplicate):**
- **crm-build-standard** — supplies `contacts`, `deals`, `companies`, the `activities` timeline, and the
  encrypted-field helpers. This skill adds proposals/projects/project_tasks/retainers/referrals and the
  lifecycle logic. Build the CRM first.
- **wire-payment-collect-reconcile** — the settlement trigger. `activateOnboarding()` is exported here
  and CALLED by `receiveWirePayment` there. If you settle by card instead, call `activateOnboarding` from
  your paid-order webhook. This skill does not collect money; it reacts to a confirmed payment.
- **google-oauth-connector** — the Drive folder + (for meetings) Calendar event use its access token.
  Do not re-implement the OAuth flow; just call `getGoogleAccessToken(env)`.
- **fail-closed-onboarding-gate** — if go-live must wait on KYC/vetting, gate `activateOnboarding` behind
  that state machine rather than firing it straight off payment.

## Reference implementation (ronininc — open and confirm before lifting)
Catalog pointer: `CRM_SKILLS_CATALOG.md` → "services-delivery-lifecycle".
All in **`worker/business-apps.ts`**:
- `settings(env)` — reads the singleton `business_settings` row (deposit %, retainer default, review
  URL, wire fields). **Throws if the row is missing** — the migration must seed it. L24–28.
- `businessSummary(env)` — one-shot rollup across contacts/replies/meetings/proposals/projects/
  retainers/referrals/booked-value/pending-wires. L30–55.
- `saveProposal(req, env, me)` — draft a proposal; `deposit_cents = round(amount * deposit_percent/100)`
  with `deposit_percent` defaulting to `settings.default_deposit_percent`; **scope encrypted** via
  `encField`; writes a `proposal` activity. L152–177.
- **`activateOnboarding(env, proposalId, actor)` — the idempotent on-payment hook. L179–221.** Returns
  the existing project id if one already exists for the proposal (idempotency); else creates the project
  (`status='onboarding'`), best-effort-creates the Drive folder, and in ONE `env.DB.batch` inserts the
  project, flips `proposals→'paid'` + `contacts→'customer'`, and logs a `payment` activity; then seeds 5
  default `project_tasks`. Note the task list is defined inline (L216).
- `listProjects` / `updateProject` / `updateProjectTask` — the board; **`updateProject` on
  `status='completed'` does `INSERT OR IGNORE` a `retainers` row (`'proposed'`) and a `referrals` row
  (`'due'`, carrying `settings.review_url`).** L295–341.
- `listRetainers`/`updateRetainer`, `listReferrals`/`updateReferral` — the recurring-revenue + referral
  lanes with their status enums. L343–379.
- (`saveMeeting`/`bookMeeting` L70–135 create a Google Calendar + Meet event — that's the booking side;
  the self-schedule engine is its own skill.)
- **`migrations/0012_business_apps.sql`** — `business_settings` (seeded `'default'` row),
  `meetings`, `proposals`, `projects` (**`proposal_id` UNIQUE** — the idempotency backbone),
  `project_tasks`, `retainers` (**`project_id` UNIQUE**), `referrals` (**`project_id` UNIQUE**),
  `reactivation_queue`.
- **Routing:** `worker/admin.ts` **L350–370** — the `business/*` routes (proposals, projects,
  project/task, retainers, referrals, settings), gated behind `crm` in `SUB_SECTION` (`business` →
  `crm`, `auth.ts` L177).
- **UI:** `public/admin/admin.js` **L457–545** — `loadProposals`/`proposalCard`,
  `loadProjects` (kanban + task chips), `loadRetainers`, `loadReferrals`.

## How to reapply it
1. **Migration.** Copy `0012_business_apps.sql`. Keep the `INSERT OR IGNORE INTO business_settings
   ('default')` seed. Keep the three UNIQUE constraints — `projects.proposal_id`, `retainers.project_id`,
   `referrals.project_id` — they are what make onboarding and completion re-runnable safely. If you
   settle by wire, also apply `0013` (see wire-payment-collect-reconcile).
2. **Proposals.** Lift `saveProposal` + `listProposals`. Keep the deposit math driven off settings and
   the `encField(scope)` on write / `decField` on read.
3. **The onboarding hook.** Lift `activateOnboarding` verbatim. Preserve: the existing-project early
   return; the single `env.DB.batch` that inserts the project AND flips both statuses AND logs the
   activity atomically; the best-effort Drive folder in its own try/catch (a Drive failure must NOT block
   onboarding); the seeded task checklist. Export it so your payment path can call it.
4. **Board.** Lift `listProjects`/`updateProject`/`updateProjectTask`. Keep the completion branch that
   `INSERT OR IGNORE`s the proposed retainer (amount = `project.retainer_cents || default_retainer_cents`)
   and the `'due'` referral with the review URL.
5. **Retainer + referral lanes.** Lift the list/update pairs and their status enums
   (retainer: proposed|active|paused|cancelled; referral: due|requested|replied|converted|dismissed).
6. **Routes + gate.** Register the `business/*` routes behind your CRM section's clearance. **No cron is
   needed** — the whole lifecycle is event-driven (payment fires onboarding; a status change fires the
   completion loop). (The only cron in this file, `runBusinessAutomations` at index.ts:189, drives the
   separate dormant-reactivation feature, not delivery.)
7. **UI.** Copy the four `load*` renderers: proposal cards with the "prepare wire / open payments"
   affordance, the project kanban with clickable task chips, and the retainer/referral status selects.

## Gotchas (from the code)
- **Onboarding idempotency lives in two places — keep both.** `activateOnboarding` first
  `SELECT id FROM projects WHERE proposal_id=?` and returns early if found; and `projects.proposal_id`
  is UNIQUE at the schema level. Either alone is fragile; together a double-fire of the payment event
  (e.g. a retried webhook, or a "mark received" clicked twice) opens exactly one project.
- **The Drive folder is best-effort, and there is no real retry.** The fetch is wrapped in try/catch and
  the project is created with `drive_folder_id = null` on failure. The UI copy says it "will be retried
  when Drive access is available," but nothing in the code retries — a folder is only attempted at
  onboarding time. If you need retry, add it explicitly; don't assume the UI text reflects behavior.
- **`settings()` throws when the singleton row is absent.** Every proposal/onboarding path funnels
  through it, so a missing `business_settings('default')` row 500s the whole feature. The migration's
  `INSERT OR IGNORE` seed is load-bearing — never drop it.
- **Money is never auto-charged on completion.** The completion branch inserts the retainer as
  `'proposed'` and the referral as `'due'` — both are prompts for a human, not actions. Preserve that:
  auto-advancing a retainer to `'active'` (billing) or auto-sending a referral would cross the
  money/irreversible line the house keeps human.
- **Completion is re-runnable but one-shot per project.** `retainers.project_id` and
  `referrals.project_id` are UNIQUE and the inserts are `INSERT OR IGNORE`, so toggling a project
  back to active and completing it again won't spawn duplicate retainers/referrals.
- **Scope and notes are encrypted at rest.** `saveProposal` `encField`s scope; `listProposals`/
  `listMeetings` `decField` on read. If `ENCRYPTION_KEY` is unset (local dev) the helpers pass text
  through in the clear and tolerate plaintext — so seed/dev data still reads, but production must set the
  secret or "encrypted" is a no-op.
- **The activities feed is the audit trail.** Every stage (proposal drafted, payment/onboarding, project
  status, meeting) writes an `activities` row (some `encField`-ed). Keep those inserts — they are how the
  contact timeline and any downstream audit reconstruct what happened, and several are inside the same
  batch as the state change so they can't drift apart.
