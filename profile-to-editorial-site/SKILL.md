---
name: profile-to-editorial-site
description: >-
  A server-side pure function that turns a validated COMPANY PROFILE (name, headline, audience, about, a
  list of services, contact + logo) into a COMPLETE single-file, responsive, dark "editorial" website —
  string in, whole HTML document out — with an embedded inquiry form that hands submissions to the host
  CRM. This is the render engine behind an "App Forge"-style generator that spins up a real company site
  from structured data, versioned (`template:'editorial', version:1`) so more templates slot in behind the
  same parse→render seam. It hard-validates the profile (field length caps, 1–8 services, a logo path that
  must be an existing /assets image, an email-shape check) and returns the list of MISSING optional fields
  so the caller can prompt for them. Use WHENEVER a build must "generate a website from a company's
  info/profile", "spin up a site from these fields", "an App Forge / site generator that emits real HTML",
  "make a one-file company site from structured data", or "let the CRM produce a prospect's site from
  recon" — i.e. a PROGRAMMATIC site render, not a hand-built bespoke design. It COMPLEMENTS
  website-build-standard (that is the house METHODOLOGY for hand-crafting a premium client site; THIS is the
  code-generated, data-driven renderer for a productized generator — reach for that when a human is
  designing, this when a machine is emitting), business-profile-recon (which SOURCES the real profile fields
  this consumes), and self-schedule-booking / idempotent-public-submission (where the embedded inquiry
  lands). Guardrails: every profile field is HTML-escaped before it hits the template (the profile is
  untrusted data); the logo must match an existing /assets image path — no arbitrary/remote URL; only the
  implemented template is accepted (unknown style throws, never renders a broken page).
---
# Profile → Editorial Site — structured company data becomes a whole website, in one function

## What it is / when to use / what it composes with
A two-part seam — `parseSite(input, style)` (validate + normalize a company profile) and
`renderEditorial(site)` (emit a complete `<!doctype html>` document as a string) — that lets a Worker (or
any server) GENERATE a real, deployable company website from structured fields instead of a designer's
hands. It is the engine an App Forge sits on: recon or an operator supplies the profile, the generator
returns a single self-contained HTML file (inlined CSS, responsive, dark editorial look, an inquiry form
wired to the host's booking/inquiry endpoint). Reach for it whenever the deliverable is "a site produced
FROM data," and the profile is untrusted input that must be validated and escaped.

**Composes with:** **website-build-standard** (the premium hand-build standard — this is its programmatic
counterpart; a human-designed flagship uses that, a data-generated prospect/company site uses this),
**business-profile-recon** (verified real fields in → don't render placeholders), and
**self-schedule-booking** / **idempotent-public-submission** (the inquiry form posts to whichever the host
provides; in an iframe it `postMessage`s the parent CRM, else it falls back to a same-origin `/api/booking`
POST). The versioned template seam means additional templates register alongside `editorial` without
touching callers.

## Reference implementation — EXACT source
`ronininc-site/worker/forge-site.ts` (the first reusable website renderer behind the App Forge):
- The data contract — `worker/forge-site.ts:2-6` (`CompanyProfile`, `EditorialSite` with `template`/
  `version`/`company`/`missing`).
- HTML-escape helper applied to EVERY field — `worker/forge-site.ts:7` (`esc`).
- **`parseSite` — the validator/normalizer**: `worker/forge-site.ts:8-23` — rejects a non-`editorial`
  style (`:9`), requires an object (`:10`), length-caps + trims each field via a `field(key,max,required)`
  closure (`:12-17`), enforces **1–8 services ≤240 chars** (`:18`), validates the email shape (`:20`),
  constrains the logo to an existing `/assets/…(png|jpg|jpeg|webp|svg)` path (`:21`), and returns the list
  of MISSING optional fields (`:22`).
- **`renderEditorial` — the single-file document**: `worker/forge-site.ts:24-34` — inlined `:root` CSS
  tokens + responsive/reduced-motion media queries (`:27`), nav/hero/services/about/contact sections built
  by escaping `company` fields (`:28`), and the embedded inquiry form + its script (`:28-33`).
- The embedded form's submit path — `worker/forge-site.ts:29-32`: iframe → `parent.postMessage({type:
  'forge:inquiry',…})` with a 20s timeout awaiting `forge:inquiry-result`; standalone → same-origin
  `fetch('/api/booking', …)`. A honeypot field (`website_hp`, `:28`) and `aria-live` status round it out.
- Wiring: consumed by the forge orchestrator — `worker/forge.ts:16` (import), `:127` (`renderEditorial`),
  `:230,245` (`parseSite` in the plan/build endpoints).

## How to reapply — the schema + THE INVARIANT
1. Define the profile contract and a `parseSite(input, style)` that throws on any invalid field, caps every
   length, constrains the logo to an existing asset path, and RETURNS the `missing` optional fields (so the
   caller can ask for them) rather than silently rendering blanks.
2. `render<Template>(site)` returns a COMPLETE self-contained HTML string — inline the CSS, make it
   responsive + reduced-motion aware, and build every visible node by passing the profile field through
   `esc()`. No external build step, no framework.
3. Embed the inquiry form so the generated site routes leads back to the host: `postMessage` to the parent
   when framed (the CRM preview/editor), with a same-origin POST fallback when the page stands alone. Add a
   honeypot + an `aria-live` status line.
4. Version the template (`template`, `version`) and gate on style so `parseSite` accepts only implemented
   templates — a new look is a new `render*` behind the same seam.
5. **THE INVARIANT:** the company profile is UNTRUSTED data. Every field is escaped before it enters the
   template and the logo is restricted to a known `/assets` path — a generated site can never inject markup
   or reference an arbitrary/remote resource, no matter what the profile says.

## Gotchas — real pitfalls from the code + how it's validated
- **Escape everything, every time.** A profile is operator/recon input; `renderEditorial` wraps each field
  in `esc()` (`worker/forge-site.ts:28`). One un-escaped field is stored XSS in a page you then deploy.
- **Constrain the logo, don't trust a URL.** `parseSite` only accepts an existing `/assets/…` image path
  (`:21`) — never a remote/arbitrary URL — so the generated site can't be pointed at an off-site asset.
- **Fail loudly on an unimplemented template.** `parseSite` throws for any style ≠ `editorial` (`:9`)
  instead of emitting a half-rendered page; add the `render*` before you accept the style.
- **The framed vs standalone form must degrade.** In the CRM iframe the form waits for a
  `forge:inquiry-result` ack with a 20s timeout (`:29-32`); standalone it POSTs `/api/booking` directly —
  test BOTH, or a previewed site's form silently hangs. Validated by rendering a fixture profile and
  confirming the document parses, the `missing` list is right, and a submitted inquiry reaches the CRM.
- **`renderEditorial` is a pure `string`→`string`.** It touches no DB and no network, so it's trivially
  unit-testable and safe to call anywhere (preview, deploy, snapshot) — keep it that way; do side effects
  in the caller.
