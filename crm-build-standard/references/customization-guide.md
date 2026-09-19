# Customizing the CRM — the only four things that differ per client

Everything below the record model is reused. A new client CRM is these four decisions + the schema
edit. Work them with the client before provisioning.

## 1. The record model (`starter-schema.sql`)
What is an entity here, and what do you know about it?
- Rename `contacts` and its `kind` to the vertical: **customer** (retail/commerce), **lead**
  (lead-gen), **member** (portal/community), **intake** (service firm), **investor**, **student**.
- Add domain fields as columns (e.g. `case_type` + `incident_date` for PI; `tier` + `spend` for
  wholesale; `position` for investors). Keep `tenant_id`, the text id convention, and the append-only
  `activities` log — the intelligence layer and the shard router depend on them.
- Keep big bytes out of rows → `media_objects` + R2.

## 2. The pipeline (`pipeline_stages`)
The stages a record moves through, as DATA not code. Examples:
- **Service/sales:** new → contacted → qualified → proposal → won / lost.
- **PI lead-gen (case-plug):** captured → consented → matched → billed.
- **Wholesale (pineapple):** prospect → first-order → repeat → at-risk → churned.
- **Support/portal:** onboarding → active → dormant.
Each stage change writes an `activities` row (`kind:'stage_change'`). Stage transitions are where you
hang triggers (notify owner, start a dialer session, send a governed draft).

## 3. Roles + visibility (`cf-identity`)
Map the role ranks to the client's team: who is **owner** (full), **admin** (manage records + staff),
**staff** (their own/assigned records). Enforced in the Worker (SQLite has no RLS). Decide whether
staff see all records or only `owner_user_id = me`.

## 4. Channels + intelligence + outreach (each behind its guardrail)
- **Capture channels:** which `cf-forms` (contact, booking, lead, RSVP) feed the CRM.
- **Intelligence** (`references/intelligence/`): pick what fits and write the feature extractors —
  - **scoring** → lead-conversion / churn / reorder propensity (pure-JS, explainable, no egress);
  - **forecasting** → reorder/demand or cost/duration off the `activities`/ledger series;
  - **semantic** → dedup + "find similar" + recommendations (Vectorize);
  - **assist** → summarize a record, draft outreach, classify/route inbound (governed, never sends).
- **Outreach:** wire `references/power-dialer.md` only if the client makes outbound calls.

### The guardrails (non-negotiable, decided here)
- **Regulated finance (e.g. an investor CRM):** ⛔ no personalized predictions/advice, no scoring of
  securities/portfolios. Non-advisory analytics only (data-quality flags, descriptive summaries).
- **Minors' data (e.g. a youth community):** ⛔ no ML over message content without a safeguarding +
  consent review. Metadata-only signals, default-off, human-in-the-loop.
- **Lead scoring anywhere:** it PRIORITIZES, it never DENIES service, and it runs AFTER the hard
  compliance gates (DNC/consent), never before.

## Worked example (one line each)
- **Restaurant/wholesale:** customers + reorder pipeline; scoring=churn, forecast=reorder+hot-set,
  assist=member summary. No special guardrail.
- **PI law leads:** leads + (captured→matched→billed); scoring=viability (prioritize only),
  semantic=attorney match, assist=intake classify/extract. Compliance gates stay authoritative.
- **Investor portal:** investors + holdings; **non-advisory only** — data-quality flags + descriptive
  summaries; NO return/price prediction.
- **Youth community:** members + conversations; **metadata-only** safety signal, default-off; no
  content ML.

## The rule
If a customization request would have you rewrite auth, capture, the API, the database, or deploy —
stop. That's a composed skill's job. You only ever write: the schema edit, the pipeline config, the
role map, and the per-model feature extractors.
