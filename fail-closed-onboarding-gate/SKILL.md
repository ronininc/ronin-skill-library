---
name: fail-closed-onboarding-gate
description: >-
  A multi-condition activation state machine that NEVER auto-approves: an entity (user / account /
  investor / applicant) becomes ACTIVE only when ALL independent gates clear (e.g. accreditation
  verified AND AML/KYC cleared AND subscription/agreement executed), each determination recorded
  with who + when, every change appended to an IMMUTABLE event log, plus a PII-minimal per-user
  document vault — on a Cloudflare Worker + D1. The subject submits/attests; a HUMAN reviewer (or a
  connected vendor) records the real determination; activation is refused with a 409 + the exact
  list of unmet conditions until the gate is satisfied. Use WHENEVER activation must wait on
  several independent approvals that a human/vendor signs off: "KYC/AML gate", "accreditation
  check", "onboarding approval", "don't activate until verified", "compliance case", "application
  review workflow", "multi-step approval before go-live", "eligibility gate", "vetting flow", or
  any regulated/high-trust onboarding. Full-stack. EXTENDS cf-identity (the users/roles it gates)
  and pairs with append-only-audit-log. Guardrails: FAIL CLOSED — the gate is satisfied only when
  every condition is explicitly cleared, and any not-yet-set condition means blocked; NO status is
  ever auto-set to verified/cleared (a human or vendor records it); PII is MINIMIZED (store a
  category + attestation + a document REFERENCE, never raw SSN/tax-ID/ID numbers in D1 — sensitive
  docs live with the vendor out-of-band); every determination is logged append-only; this SUPPORTS
  compliance, it does not REPLACE the attorney / fund admin / KYC vendor / accountant.
---
# fail-closed-onboarding-gate — activate only when every condition clears

## What it is / when to use
A system of record for a multi-gate onboarding: the subject submits attestations, a reviewer records
each real determination, and the entity can only be flipped ACTIVE when every independent condition
is cleared — otherwise activation is refused with the precise list of what's missing. Every change
is appended to an immutable log, and delivered documents live in a per-user vault. Use it for any
onboarding where "active" must wait on several human/vendor approvals (KYC/AML, accreditation,
signed agreements, background checks, credentialing).

## Reference implementation (Wavelygth — lift from here)
- **Backend** — `~/Projects/clients/wavelygth/worker/index.js` L2740-2876
  - Enums L2740-2742: `ACCRED_CATEGORIES`, `DOC_KINDS`, `CDOC_MAX` (~1.5 MB inline doc cap).
  - `complianceCase(env, userId)` L2744-2752 — get-or-create the case row (INSERT OR IGNORE).
  - `ceLog(env, userId, kind, status, detail, actor)` L2753-2756 — **append-only** event write
    (never updates, never throws the request).
  - `caseGate(c)` L2757-2763 — **THE fail-closed gate**: builds a `missing[]` and is `ok` only when
    accreditation==='verified' AND aml==='cleared' AND subscription==='executed'. Any other/blank
    value ⇒ blocked.
  - `checklist(c)` L2764-2771 — the subject-facing step list with done flags.
  - Subject-facing: `handleComplianceMe` L2774-2779, `handleAccreditationSubmit` L2780-2789
    (requires `attest===true`; records `method='self_attested'` + a category, status⇒`submitted`,
    NOT verified), `handleAmlSubmit` L2790-2799 (legal name + country + source-of-funds; **explicit
    "don't enter your SSN here"**), `handleEconsent` L2800-2807, doc reads L2808-2816.
  - Admin: `handleComplianceList` L2819-2827 (includes investors with NO case yet as all-blocked),
    `handleComplianceReview` L2828-2851 (a reviewer sets each field to a whitelisted status,
    stamping `verified_by`/`verified_at` only on the positive value; validates the status set;
    logs + audits), `handleComplianceActivate` L2853-2863 — **re-checks `caseGate` and returns
    `409 { missing }` if not satisfied** before setting `funded=1`, `handleComplianceDeliverDoc`
    L2864-2876 (writes to the vault, size-capped, logged).
  - Routes: subject L3130-3135, admin L3241-3244, all behind the admin gate L3172; anonymous ⇒ 401.
- **Schema** — `~/Projects/clients/wavelygth/worker/migrations/0012_compliance.sql`:
  `compliance_cases` (per-condition status + who/when columns + `funded` gate result + `econsent`),
  append-only `compliance_events`, and `investor_documents` (the PII-minimal vault). The file's
  header comment states the guardrails: supports-not-replaces the attorney/fund-admin/vendor, no
  auto-verify, minimal PII (category + attestation + doc reference, never raw SSN/tax data).
- **UI** — `~/Projects/clients/wavelygth/portal/index.html`: admin review queue `loadCompliance`
  L1692-1730 (status chips + per-field decision buttons + an Activate button **disabled until
  `gate.ok`** + "to activate: <missing>"); subject onboarding forms `loadOnboarding` L1733-1768
  (checklist + accreditation/AML/e-consent forms + document vault viewer).
- **Proof** — `~/Projects/clients/wavelygth/worker/lib/_proof/compliance.test.mjs`: proves fresh
  case = gate closed; activate blocked (409, all three missing); still blocked with only 2 of 3;
  all three cleared ⇒ activation succeeds; tenancy (another user sees none of it); investor can't
  read the admin queue (403) or activate (403); anonymous ⇒ 401.

## How to reapply it
1. **Migration:** copy `0012_compliance.sql`. Rename `compliance_cases` columns to YOUR conditions
   (each one gets a `<cond>_status` + `<cond>_verified_by`/`_at`), keep the append-only events table
   and the doc vault. Keep the "final gate result" boolean (`funded` → e.g. `active`).
2. **Gate:** copy `caseGate(c)` — the ONE function that decides activation. It builds `missing[]` and
   is `ok` only when every condition is at its cleared value. This is the fail-closed heart.
3. **Reviewer flow:** copy `handleComplianceReview` — whitelist the allowed statuses per field,
   stamp who/when only on the positive determination, `ceLog` every change. Copy
   `handleComplianceActivate` — **re-run the gate and 409 with `missing` if not satisfied**; never
   trust the client's "gate ok".
4. **Subject flow:** submit/attest endpoints set status to `submitted`, NEVER to `verified/cleared`.
   Require the attestation checkbox. Keep the "don't submit your SSN here" copy.
5. **UI:** disable the Activate control until `gate.ok`, and show the missing conditions inline.
6. **Prove it:** copy `compliance.test.mjs`'s shape — assert 409-with-all-missing, the partial
   block, the success only when all clear, and the tenancy/role/anon negatives.

## Gotchas (from the code + comments)
- **Fail CLOSED.** `caseGate` is `ok` only when EVERY condition is explicitly at its cleared value;
  a blank/`not_started`/`submitted`/`pending` is blocked. Never invert this to "ok unless a flag
  says no".
- **Never auto-verify.** Submit/attest endpoints only move a condition to `submitted`. A human
  reviewer (or a vendor callback) records `verified`/`cleared`/`executed`. The subject can't clear
  their own gate.
- **Re-check the gate at activation, server-side.** The UI disables the button, but
  `handleComplianceActivate` re-runs `caseGate` and 409s regardless — the button state is a hint,
  not the enforcement.
- **Minimize PII.** Store a category + attestation + a document *reference*, never raw SSN / tax
  data / ID numbers in D1. Sensitive verification docs stay with the vendor out-of-band. The AML
  form literally tells the user not to enter their SSN.
- **Append-only log.** `ceLog` only ever inserts (who/what/when/actor) and is wrapped so a log
  failure never breaks the request — a regulated firm must be able to show its work.
- **Include not-yet-started subjects as fully-blocked** in the admin list, so someone with no case
  row doesn't silently look activatable.
- **This SUPPORTS compliance; it does not REPLACE** the securities attorney, fund administrator,
  KYC/AML vendor, or accountant. It is the state machine + record, not the legal determination.
- Enforce the whole surface with role checks: subject sees only their own case (tenancy), admin
  reviews, anonymous is 401 — all proven in the test.
