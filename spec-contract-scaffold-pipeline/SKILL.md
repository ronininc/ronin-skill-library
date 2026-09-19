---
name: spec-contract-scaffold-pipeline
description: >-
  Turn a plain-language description into a real, runnable app/artifact through a multi-stage pipeline
  bound by ONE validated JSON contract ("the spec"): every stage reads and writes the same spec, and a
  DETERMINISTIC built-in generator is the floor that ALWAYS yields a working result — stronger engines
  (an LLM planner, an agent code-writer, a real backend, an auto-deploy) UPGRADE the output when
  configured and HONESTLY DEGRADE (logged, never faked) when not. Use WHENEVER a build must "generate an
  app/site/form/schema from a prompt or a form of intake", "describe it and get a working thing",
  "scaffold a CRUD app from a description", "spec-driven generator", "prompt-to-app", "let a model draft
  the structure but never depend on it", or any tool where a natural-language (or structured) request
  becomes a generated artifact. The reusable core is the SPEC-AS-CONTRACT discipline + deterministic
  floor + honest engine ladder — NOT any product/billing/paywall around it. COMPLEMENTS
  collision-safe-identifier-derivation (how the spec's names become safe DB/storage identifiers),
  untrusted-preview-sandbox (how to preview the generated artifact safely), pluggable-draft-brain (the
  swappable LLM seam the planner stage can call), single-source-data-embed and crm-build-standard /
  website-build-standard (what the scaffold can target). Guardrails: never claim an output the pipeline
  did not produce; the deterministic generator must run with ZERO model/backend/deploy config; a stronger
  engine that fails must fall through to the floor, not ship a partial artifact.
---

# Spec-Contract Scaffold Pipeline — prompt → validated spec → real artifact, always

## What it is / when to use / what it composes with
A build discipline for any "describe it and get a working thing" feature. The whole pipeline is glued by
a single JSON document — the **spec** — that is schema-validated and passed unchanged between stages:

```
NL prompt ─▶ 1 PLAN (model→spec, or deterministic heuristic→spec)
          ─▶ 2 PROVISION backend (real migrations/collections if configured, else local storage)
          ─▶ 3 GENERATE (agent code-writer if configured, else deterministic schema-driven generator)
          ─▶ 4 PACKAGE (zip) + PREVIEW
          ─▶ 5 DEPLOY (optional) ── every stage appends a human-readable step
```

Two invariants make it reusable and safe:
1. **Spec-as-contract.** One validated JSON shape is the only thing stages share, so any stage can be
   swapped without touching the others. The generated artifact ships the spec as its own source of truth.
2. **Deterministic floor + honest ladder.** A dependency-free built-in generator always produces a real,
   runnable artifact with zero external config. Stronger engines are strictly optional upgrades; when one
   is absent OR fails, the pipeline logs it and falls through — it never fabricates a result.

Use it for: prompt→app/site builders, "generate a form/schema/dashboard from a description", intake→
scaffold tools, or any codegen feature that must degrade to something real offline. Do NOT lift the
surrounding product shell (billing, gating, paywall) — that lives in other skills (`cf-identity`, the
lead-engine billing pattern). This skill is the plumbing between prompt and artifact.

Composes with: **collision-safe-identifier-derivation** (turns spec names into unique DB/storage keys),
**untrusted-preview-sandbox** (serves the generated HTML safely), **pluggable-draft-brain** (the swappable
model seam the planner can use instead of a single hard-wired client), **crm-build-standard** /
**website-build-standard** / **commerce-spine** (targets the scaffold can emit toward).

## Reference implementation (apps/appforge — a prompt→app builder; OPEN these)
- **The contract + validation** — `apps/appforge/backend/app/forge/spec.py`:
  `APP_SPEC_SCHEMA` (15-67, JSON-Schema draft 2020-12), a **dependency-free fallback validator**
  `_fallback_validate` (69-112) selected when `jsonschema` is absent (115-126) so validation never
  becomes an install-gated single point of failure, and `normalize_spec` (152-172) which fills safe
  defaults and derives default pages but **never invents domain fields the planner didn't provide**.
- **Stage 1 — plan** — `apps/appforge/backend/app/forge/planner.py`: `SPEC_SYSTEM` (15-23) constrains the
  model to emit ONLY spec-shaped JSON; `plan` (88-95) accepts the model's output **only if it validates**,
  otherwise `heuristic_plan` (67-85) produces a real, simpler spec from keyword hints (`_ENTITY_HINTS`
  25-32) — it never fabricates fields it can't justify. `_extract_json` (37-46) tolerates prose/fences.
- **The model seam** — `apps/appforge/backend/app/model/provider.py:16-36`: an OpenAI-compatible client
  that returns `None` (not an exception, not a fake answer) when unconfigured or failing, so stage 1
  falls to the heuristic cleanly. (In a Worker build, use `pluggable-draft-brain` here instead.)
- **The orchestrator** — `apps/appforge/backend/app/forge/orchestrator.py:48-114`: the 5-stage ladder with
  a `progress(stage, pct, msg)` callback; each engine is tried, and a `NotConfigured`/failed engine
  appends a step and falls to the built-in (82-96). `BuildResult` (30-40) reports the ACTUAL plan source,
  backend and engine used — the honesty ledger.
- **The deterministic floor** — `apps/appforge/backend/app/forge/codegen_builtin.py:175-221`: renders a
  real single-page schema-driven CRUD app from the spec (one HTML template, `_GEN_APP_HTML` 19-153) with
  **zero backend**. Note the **auth-honesty gate** (180-191): the generator ships no login, so it rewrites
  the spec's `auth` to `enabled:false, implemented:false, requested:<orig>` and shows a visible notice —
  it never advertises a boundary it doesn't back. Safe injection at 200-208 (see Gotchas).
- **Optional stronger engines** (all fail → floor): `codegen_aider.py:20-50` (rejects a nonzero-exit run
  so a partial file never ships — 43-44), `codegen_openhands.py:21-30`, `baas_supabase.py:29-78` (renders
  real SQL migrations), `baas_pocketbase.py:34-63` (returns `None` on any failure, never fakes success),
  `deploy_coolify.py:16-30`.
- **Background runner + live progress** — `apps/appforge/backend/app/jobs/runner.py`: `_execute` (139-195)
  runs a build on a worker thread and writes progress to the job row so a poller sees it live; a failure
  marks the row `error` (176-189) so a build **never hangs**; bounded pending queue (`_reserve_slot`
  45-73 → HTTP 429) and oldest-first artifact eviction (`_evict_finished_builds` 96-136) bound compute+disk.
- **Poll UI** — `apps/appforge/frontend/index.html:243-259`: start build → poll `GET /builds/{id}` every
  ~1.4 s → render stage/percent/steps → deliver preview + download links on `done`, honest message on `error`.
- **Proof (hermetic, no network)** — `apps/appforge/backend/tests/test_forge.py`: heuristic spec validates
  (18-21), floor produces a runnable app (24-31), auth honesty holds (34-57), and `run_build` end-to-end
  yields a zip with `index.html` + `app-spec.json` and a step that's honest about the fallback (60-73).

## How to reapply (in a CLIENT build)
1. **Define the spec first.** Write the smallest JSON shape that fully describes the artifact (e.g.
   `{name, entities:[{name, fields:[{name,type,required}]}], pages, auth}` for a CRUD app; a different
   shape for a form/site/dashboard). Give it a JSON-Schema **and** a hand-rolled fallback validator so
   validation works even where the schema lib isn't installed. This document is the ONLY thing stages share.
2. **Write the deterministic generator BEFORE any model.** Make it turn a valid spec into a real, runnable
   artifact with zero external services. This is your floor and your test fixture; everything else is an
   upgrade. Prove it with a hermetic test that runs offline.
3. **Add the planner as an optional upgrade.** Constrain the model to emit spec JSON only, then accept it
   **only if it validates**; on missing model / invalid output, fall to a deterministic heuristic that
   still yields a real spec. Route model calls through `pluggable-draft-brain` in a Worker build.
4. **Make every other engine `NotConfigured`-or-fail → floor.** Wrap real-backend provisioning, agent
   codegen and deploy so absence or failure appends a log step and falls through — never a partial ship.
5. **Run it as a job with live progress.** Background-thread (or queue) the build, write stage/percent/step
   to a row, poll it from the UI, mark `error` on any exception so nothing hangs, and cap pending work +
   evict old artifacts if builds persist to disk.
6. **Report what actually happened.** Return the real plan source / backend / engine used and surface the
   step log; the artifact carries its own spec so it can be regenerated or wired to a real backend later.

## Gotchas
- **The spec is untrusted input** (a prompt produced it). When you inject it into generated HTML, escape
  for the `<script>` context (`<`→`<`, `>`→`>`, `&`→`&`) and HTML-escape any name that
  lands in markup — `codegen_builtin.py:200-208`. A crafted prompt must not break out into the page.
- **Never advertise a capability the floor doesn't implement.** The auth-honesty gate is the canonical
  example: preserve the *requested* intent in the spec, but flip `enabled/implemented` to the truth and
  show a notice. Same rule for "connected to a backend" — the built-in app uses local storage, so report
  backend as local even after rendering migrations (`orchestrator.py:64-76`).
- **A nonzero exit from an agent code-writer means a broken/partial artifact — reject it and fall to the
  floor** (`codegen_aider.py:43-44`); shipping a half-written file is worse than the deterministic result.
- **`normalize_spec` must be idempotent** (re-running reproduces the same slugs/pages) — use
  collision-safe-identifier-derivation for the name→identifier step, or two names that normalize alike will
  silently share one storage key / DB column.
- **Bound the job system.** Without a pending cap one caller floods the queue; without artifact eviction
  the disk fills. Cap per-caller + global, and evict oldest-first while KEEPING the history row (mark it
  evicted) so a later poll/download reports a clean "gone", not a 500 on a dangling path.
