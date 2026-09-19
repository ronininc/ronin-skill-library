# House Skill-Atoms Index — mix and match

Our big skills each bundle many capabilities. This index **decomposes them into atoms** — the
smallest independently-useful units (one mechanism, widget, gate, table, or step) — so a build pulls
exactly the parts it needs and shared building blocks become visible and reusable.

**Schema.** Each skill lists its atoms:
> **atom-name** — one-line capability. `deps:` other atoms/skills · `reused-by:` where else it helps

Atom names are kept consistent across skills, so the same block appearing in two skills reads with
the **same name** (that's how you spot the shared foundations — see *Shared atoms* at the end).

Status: **web-effects-catalog** and the **anthropic-skills web/content/lead** families are authored
here from source/manifests. The **Cloudflare / commerce / CRM / lead** standalone skills are being
deepened by a background read-through and will be folded in verbatim.

---

## Motion & interaction — `web-effects-catalog`
_Sovereign, accessible, reduced-motion-safe animation library (this skill)._
- **reveal-on-scroll** — slide/fade/zoom blocks in on viewport entry, visible-by-default. `deps: none` · `reused-by: every site`
- **exploded-view (`xv`)** — hover/tap an item; parts blow apart, float, coalesce; per-part labels. `deps: tilt (shared helper)` · `reused-by: menus, product/portfolio, furniture, gadgets, the Solomon engine map`
- **tilt** — pointer-driven 3D card/media tilt. `deps: none` · `reused-by: xv, product cards, hero media`
- **parallax** _(roadmap)_ — scroll-linked layer depth. `deps: none` · `reused-by: heroes, section dividers`
- **marquee/ticker** _(roadmap)_ — infinite scrolling strip. `deps: none` · `reused-by: news, menu specials, logo walls`
- **flip-card** _(roadmap)_ — CSS 3D flip front↔back. `deps: none` · `reused-by: services, team, product back-of-card`
- **sticky-header** _(roadmap)_ — shrink/condense header on scroll. `deps: none` · `reused-by: every site`
- **count-up** _(roadmap)_ — odometer number roll (real data only). `deps: reveal-on-scroll` · `reused-by: stats, dashboards`
- **carousel** _(roadmap)_ — Swiper-free hero/testimonial slider. `deps: none` · `reused-by: heroes, reviews`
- **cursor-spotlight** _(roadmap)_ — pointer-following radial light. `deps: none` · `reused-by: heroes, CTAs`

## Web foundation — `website-build-standard` (anthropic-skills)
_The base every client/team site is built on._ (manifest-derived; deepen on read)
- **self-contained-page** — single `index.html` + `/assets/` + `README.md`, Cloudflare-static ready. `deps: none` · `reused-by: all site skills`
- **immersive-centerpiece** — physically-explorable hero with a 2D standard-mode fallback. `deps: none` · `reused-by: immersive-evidence-workspace, sports`
- **builder-edit-media** — builder-only drag-and-drop photo/MP4-per-slot editor, locked for visitors. `deps: none` · `reused-by: immersive-evidence-workspace`
- **hero-slideshow** — cinematic slideshow of the client's best photos as default hero. `deps: none` · `reused-by: all site skills`
- **image-inspector** — click-to-zoom media inspector. `deps: none` · `reused-by: galleries, menus`
- **svg-logo** — scalable SVG logo handling. `deps: none` · `reused-by: all`
- **payment-ready-shop** — a shop scaffold ready to wire to a processor. `deps: commerce-spine (for the brain)` · `reused-by: commerce sites`
- **inquiry-routing** — per-site destination for inquiries. `deps: cf-forms` · `reused-by: all`
- **group-community-link** — group/community link slot. `deps: none` · `reused-by: all`
- **video-latency-rules** — hero-video loading/latency discipline. `deps: none` · `reused-by: site-media-fetch outputs`

## Recon & content — anthropic-skills
- **`business-profile-recon`** — _reach a real business's live profiles before writing its facts._
  - **profile-reach** — pull verified facts from owner.com / Google Business Profile / Yelp / socials / delivery platforms. `deps: none` · `reused-by: website-build-standard, custom-lead-generator, crm-build-standard`
  - **fact-citation** — cite or flag every stated fact; never placeholder a named business. `deps: profile-reach` · `reused-by: all client copy`
- **`site-media-fetch`** — _harvest a business's real public video/audio for its own site._
  - **public-media-harvest** — yt-dlp pull of public reels/videos/posters. `deps: profile-reach` · `reused-by: website-build-standard heroes/galleries`
  - **web-ready-prep** — transcode/poster/thumbnail prep for web slots. `deps: public-media-harvest` · `reused-by: hero-slideshow, video-latency-rules`
  - **client-upload-flag** — mark empty slots CLIENT-UPLOAD instead of fabricating. `deps: none` · `reused-by: builder-edit-media`
- **`spanish-regional-localization`** — _native-sounding regional Spanish, not textbook._
  - **regional-voice** — country/region-specific colloquial ES (Cuban/Colombian/Sinaloa/etc.). `deps: none` · `reused-by: any bilingual site, menus, ads`
- **`immersive-evidence-workspace`** — _AR product/evidence room; select to enter, evidence per item._
  - **holo-table** — ring-pedestal product table; select to zoom/enter. `deps: immersive-centerpiece` · `reused-by: portfolio/product/data-room sites`
  - **evidence-panel** — per-item sourced evidence + media view. `deps: none` · `reused-by: Solomon evidence surfaces`
  - **manifest-driven-render** — one manifest drives the whole workspace; builder-editable→locked. `deps: builder-edit-media` · `reused-by: service-business-website`
  - **guided-upload-boot** — boot-prompt for client media into fixed slots. `deps: client-upload-flag` · `reused-by: builder-edit-media`
- **`service-business-website`** — _service-vertical site preset._ (manifest-derived; deepen on read)

## Cloudflare data & auth building blocks — standalone

### `cf-identity`
_From-scratch login/signup/sessions on a Worker + D1 — a Netlify Identity / Supabase Auth clone you own._
- **pbkdf2-password-hashing** — PBKDF2-SHA256 via `crypto.subtle`, per-user hex salt, hard-capped at 100k iterations (the runtime cap that 500s in prod above it). `deps: none` · `reused-by: commerce-spine, crm-build-standard, any auth build`
- **users-sessions-schema** — D1 `users` + `sessions` tables. `deps: d1-schema+migrations` · `reused-by: commerce-spine, crm-build-standard`
- **httponly-session-cookie** — 32-byte token, HttpOnly + SameSite=Lax, Secure over https. `deps: users-sessions-schema` · `reused-by: any gated app`
- **auth-middleware (currentUser)** — cookie → `JOIN sessions→users WHERE token=? AND not expired`; protected routes 401 first. `deps: httponly-session-cookie` · `reused-by: cf-forms, cf-functions, commerce-spine, crm-build-standard`
- **roles-admin-worker** — first account bootstraps `admin`, others default `worker`. `deps: users-sessions-schema` · `reused-by: commerce-spine, crm-build-standard`
- **shared-signup-code-gate** — optional `TEAM_CODE` gating registration, constant-time compared. `deps: constant-time-compare` · `reused-by: crm-build-standard, cf-forms`
- **register-login-logout-flow** — duplicate-email reject, one generic auth error, logout deletes row + clears cookie. `deps: pbkdf2-password-hashing, httponly-session-cookie` · `reused-by: any auth build`
- **constant-time-compare (safeEqual)** — timing-safe equality. `deps: none` · `reused-by: any credential check`

### `cf-forms`
_Capture submissions into your own D1 table — a Netlify Forms clone._
- **submissions-table** — `submissions(...,data JSON,...)` + `(form,created_at)` index. `deps: d1-schema+migrations` · `reused-by: crm-build-standard, commerce-spine CRM`
- **form-post-endpoint** — `POST /api/form` (JSON or urlencoded), known vs extra split, parameterized insert. `deps: method-path-router` · `reused-by: crm-build-standard, any site`
- **honeypot-spam-check** — hidden `_gotcha`; filled → silently dropped. `deps: none` · `reused-by: any public form`
- **turnstile-verify** — optional server-side Turnstile verify. `deps: turnstile-spin` · `reused-by: any public form`
- **progressive-form-markup** — works before JS, `fetch`-enhanced inline "Thanks!". `deps: none` · `reused-by: any site`
- **admin-submissions-list** — admin-only `GET /api/submissions` behind auth. `deps: auth-middleware` · `reused-by: crm-build-standard`
- **ip-rate-limit** — optional per-IP throttle (KV/DO). `deps: KV/DO binding` · `reused-by: any endpoint`
- **form-notification** — optional email-on-submit. `deps: cloudflare-email-service` · `reused-by: crm-build-standard`

### `cf-functions`
_A serverless backend on ONE Worker that serves the static site AND `/api/*` — a Netlify Functions clone._
- **one-worker-serves-both** — `ASSETS` serves files first; `/api/*` falls through to the router. One origin, no CORS. `deps: wrangler-bindings-config` · `reused-by: every cf build`
- **method-path-router** — plain-JS routing on method+path, regex path params. `deps: none` · `reused-by: cf-forms, cf-identity, commerce-spine`
- **json-response-helper** — `json(d,status,headers)` with `no-store`. `deps: none` · `reused-by: all cf skills`
- **d1-access-pattern** — `env.DB.prepare().bind().first/all/run`, always parameterized. `deps: none` · `reused-by: all data skills`
- **secrets-config-env** — non-secret `vars` in wrangler.jsonc; secrets via `wrangler secret put`. `deps: none` · `reused-by: cf-identity, commerce-spine`
- **error-handling-wrapper** — try/catch → 500 JSON. `deps: none` · `reused-by: all`
- **spa-api-coexistence** — `run_worker_first:["/api/*"]` so an SPA catch-all can't swallow API routes. `deps: one-worker-serves-both` · `reused-by: any SPA build`
- **wrangler-bindings-config** — `main`, `compatibility_date`, `assets`, `d1_databases`. `deps: none` · `reused-by: all cf builds`

### `cf-deploy`
_Preview a build as a client sees it, then put it live — a Netlify Deploy Previews + hosting clone._
- **local-client-preview** — `wrangler dev` on a port; drive via preview_start/read_page/screenshot. `deps: none` · `reused-by: every build's verify step`
- **local-d1-migrations** — `migrations apply --local`. `deps: d1-schema+migrations` · `reused-by: all data builds`
- **remote-d1-create** — `wrangler d1 create` → paste `database_id`. `deps: none` · `reused-by: commerce-spine, crm-build-standard`
- **remote-migrations-apply** — `migrations apply --remote`. `deps: remote-d1-create` · `reused-by: all data builds`
- **secret-put** — `wrangler secret put`, never committed. `deps: none` · `reused-by: cf-identity, commerce-spine`
- **worker-deploy** — `wrangler deploy` → `*.workers.dev`. `deps: none` · `reused-by: all`
- **pages-deploy** — static-only `pages deploy ./public`. `deps: none` · `reused-by: brochure sites`
- **custom-domain-binding** — route/`custom_domain` + DNS (apex+www). `deps: worker-deploy` · `reused-by: all`
- **deploy-safety-gate** — every remote step needs the operator's explicit go-ahead; verify the live site serves the new build (don't trust a green log). `deps: none` · `reused-by: commerce-spine, crm-build-standard, all`

### `commerce-spine`
_Sovereign DB-backed commerce + CRM brain + processor-agnostic checkout (per-site Worker + D1 node)._
- **per-site-d1-node** — companion Worker + D1 the page talks to; ships empty-ready even on brochure sites (no retrofit). `deps: cf-functions, cf-deploy` · `reused-by: crm-build-standard (data brain)`
- **unlimited-catalog + hot-set-pos-syncer** — D1 is source of truth; syncer pushes the sellable window (≤ POS cap) into the POS, bypassing the ~15k item ceiling. `deps: per-site-d1-node, inventory-ledger` · `reused-by: crm-build-standard`
- **pos-reconciliation-sync** — POS webhooks decrement master + write a ledger row. `deps: inventory-ledger, idempotent-webhooks` · `reused-by: crm-build-standard`
- **inventory-ledger** — append-only ledger row in the SAME txn as every stock change; cached qty is convenience, ledger is truth. `deps: per-site-d1-node` · `reused-by: crm-build-standard`
- **money-cents + qty-milliunits** — integer cents + milli-unit quantities, no floats. `deps: none` · `reused-by: crm-build-standard, all commerce`
- **tenant-id-identity** — `${tenantId}:${kind}:${key}` in every record so tenants can't collide/leak. `deps: none` · `reused-by: crm-build-standard, d1-shard-overflow`
- **aes-gcm-at-rest** — `encField`/`decField` on sensitive columns, keyed by `ENCRYPTION_KEY`. `deps: secrets-config-env` · `reused-by: crm-build-standard`
- **worker-enforced-roles** — owner/lead/tech/worker ranks enforced in the Worker (SQLite has no RLS). `deps: cf-identity roles` · `reused-by: crm-build-standard`
- **capability-readiness-probe** — state machine (NOT_CONFIGURED→…→VERIFIED_WRITE_GATED/STALE) deciding open-vs-closed processor by real probe. `deps: none` · `reused-by: crm-build-standard, any integration honesty gate`
- **processor-agnostic-tender-driver** — swappable driver (Stripe/Square/Authorize.net/Clover Ecommerce); closed processors get no tender code. `deps: capability-readiness-probe` · `reused-by: crm-build-standard`
- **webhook-verified-payment-state** — `PAID`/refund written ONLY from a verified webhook; over-refund guard in-txn. `deps: processor-agnostic-tender-driver, idempotent-webhooks` · `reused-by: crm-build-standard`
- **pci-boundary-scanner** — card data never lands in the node; scanner on every write. `deps: none` · `reused-by: any payment build`
- **idempotent-webhooks** — dedupe on `${mId}:${objectId}:${type}:${ts}` with an `origin` tag so self-syncs don't echo. `deps: per-site-d1-node` · `reused-by: crm-build-standard, pos-reconciliation-sync`
- **fail-closed-environment** — sandbox creds can't resolve to prod; unconfigured → inert `needs_review`, never faked. `deps: none` · `reused-by: any integration`
- **d1-shard-overflow** — sticky, aggregate-root-co-located routing across `DB_1/DB_2/…` via `shard_routes`; growth is O(new), not `hash%N`. `deps: tenant-id-identity` · `reused-by: crm-build-standard scale`
- **r2-blob-offload** — fat bytes (recordings/attachments/email-HTML) → R2 + a D1 pointer (escapes the 2 MB row cap). `deps: per-site-d1-node` · `reused-by: crm-build-standard, power-dialer recordings`

### `crm-build-standard`
_Orchestrator: composes the guts skills, tailors the record model, adds governed intelligence + outreach._
- **record-model-customization** — the only per-client custom part: the entity + fields, from `starter-schema.sql`. `deps: per-site-d1-node` · `reused-by: any vertical CRM`
- **pipeline-stages-as-data** — stages are rows (config, not code), each can trigger actions. `deps: record-model-customization` · `reused-by: notion-intake-crm-cloner, any sales CRM`
- **append-only-activity-log** — every touch + stage change recorded immutably. `deps: per-site-d1-node` · `reused-by: power-dialer audit, commerce-spine`
- **three-skill-full-build-chain** — business-profile-recon → website-build-standard → this CRM → cf-deploy from REAL data. `deps: those four` · `reused-by: any full client build`
- **login-untouched-deploy-bracket** — user-count before/after, `auth.js`/`SESSION_SECRET` untouched, live 401 probe. `deps: cf-identity, cf-deploy` · `reused-by: any redeploy of an auth'd app`
- **free-tier-playbook** — free-first discipline vs named CF limits (index filters, blobs→R2, shard across 500 MB DBs, embeddings-in-D1 vs paid Vectorize). `deps: none` · `reused-by: commerce-spine scale, every CF build`
- **explainable-scoring** — pure-JS, zero-neuron conversion/churn/reorder scores that return their factors; trained offline. `deps: intelligence lib` · `reused-by: power-dialer ordering, lead-qualifier analog`
- **forecasting** — pure-JS reorder/demand/cost/duration forecasting. `deps: intelligence lib` · `reused-by: any CRM`
- **governed-llm-assist** — Workers AI summarize/draft/classify that returns `requiresApproval`, never auto-sends. `deps: Workers AI` · `reused-by: outreach drafts, power-dialer`
- **semantic-search (free + paid)** — Vectorize (paid) OR free embeddings-in-D1 + in-Worker cosine. `deps: intelligence lib` · `reused-by: any CRM`
- **governed-power-dialer** — compliance-first live-agent dialer (DNC/TCPA/consent gated in SQL, AMD, Twilio softphone, append-only audit; never predictive/robodial/spoof). `deps: cf-functions, cf-identity, telephony, explainable-scoring` · `reused-by: any outreach CRM`
- **auth-hardening (lockout + admin-2fa)** — brute-force lockout + admin TOTP, extending cf-identity. `deps: cf-identity` · `reused-by: any auth build`
- **report-generator** — periodic aggregation from D1, server-rendered. `deps: per-site-d1-node` · `reused-by: any CRM`

## Sports interaction system — `sports-website-standard`
_15-effect animation/interaction catalog + arena reference, layered on website-build-standard. The sport-themed sibling of this effects library — reduced-motion discipline is shared._
- **reduced-motion-lowpower-fallback** — mandatory 2D/instant fallback for EVERY effect. `deps: none` · `reused-by: web-effects-catalog (same doctrine), every motion build`
- **vendored-3d-no-cdn** — vendor `three.min.js` same-origin, lazy-load heavy 3D. `deps: none` · `reused-by: any 3D web build`
- **tiering-honesty-gate** — Tier-1 (always) vs Tier-2 (needs real asset/feed, else documented fallback); never fake a live score. `deps: none` · `reused-by: any capability-honest build`
- **arena-reference-model** — Desert Diamond Arena seat-map/field data as a visual reference (not a schedule claim). `deps: none` · `reused-by: seat-viewer, 50-yard scrollytelling`
- **wall-crash-page-loader** — physics loader shattering into turf. `deps: canvas/JS` · `reused-by: any dramatic loader`
- **3d-helmet-configurator** — WebGL rotate + neon reflections; needs GLB (turntable fallback). `deps: vendored-3d-no-cdn` · `reused-by: any 3D product configurator`
- **3d-virtual-seat-viewer** — WebGL camera sweep into a seat; needs seat data (2D-map fallback). `deps: arena-reference-model, vendored-3d-no-cdn` · `reused-by: any venue/seat selector`
- **neon-ribbon-board-marquee** — LED-ring news marquee. `deps: none` · `reused-by: web-effects-catalog marquee atom, any ticker`
- **parallax-mascot-breakdown** — scroll-driven layered logo assembly + chromatic aberration. `deps: none` · `reused-by: web-effects-catalog parallax, any brand reveal`
- **arcade-scoreboard-counter** — slot-machine number flips. `deps: none` · `reused-by: web-effects-catalog count-up, any KPI counter`
- **roster/stat widgets** — impact-frame player cards, 50-yard scrollytelling, ironman offense↔defense morph. `deps: none` · `reused-by: any team/staff grid, scrollytelling, A/B layout toggle`
- **shop micro-interactions** — jersey-swapper, confetti add-to-cart, sticky mini-cart, rebound-net faceted filter. `deps: none` · `reused-by: commerce-spine/website shop, any faceted filter`
- **blitz-live-ticker** — alert tray on live events; needs a real feed. `deps: live feed` · `reused-by: any live-event site`

## Lead-gen & list-building — standalone

### `lead-qualifier`
_Turns a raw lead CSV into a verified, means-tested list one lead at a time, and learns what converts._
- **csv-worklist-scaffold** — normalize any-column input (auto-detect name/company/email/phone/city/source), print per-lead searches. `deps: none` · `reused-by: az-cash-buyer-finder, any list tool`
- **identity-confirmation-gate** — confirm the *specific* person; reject namesakes → `UNVERIFIED`. `deps: web search/fetch` · `reused-by: az-cash-buyer-finder`
- **public-surface-recon** — own site → LinkedIn → IG/X/FB/TikTok, owned surfaces first. `deps: business-profile-recon` · `reused-by: az-cash-buyer-finder, crm-build-standard enrichment`
- **means-authority-rubric** — score capital + authority evidence (fund/firm, GP/principal title, deals, accredited signals). `deps: references/rubric.md` · `reused-by: any investor qualification`
- **verdict-tiers** — HIGH/MEDIUM/LOW/UNVERIFIED, each citing what was seen. `deps: means-authority-rubric, identity-confirmation-gate` · `reused-by: az-cash-buyer-finder`
- **evidence-citation** — every link/verdict sourced or blank+marked; never fabricate. `deps: none` · `reused-by: az-cash-buyer-finder`
- **verified-output-builder** — enriched CSV + xlsx with clickable verified links. `deps: none` · `reused-by: az-cash-buyer-finder`
- **outcome-learner** — transparent win-rate-per-signal learner → `model.json` + plain-English playbook. `deps: output history` · `reused-by: crm-build-standard scoring analog`
- **learned-ranking** — feed `model.json` back in → `learned_score` + `priority` re-sort. `deps: outcome-learner` · `reused-by: any lead-scoring loop`

### `az-cash-buyer-finder`
_Ranked, honest AZ (Maricopa) real-estate investor lists from public records — four distinct populations, never conflated._
- **assessor-parcel-miner** — Maricopa Assessor GIS query (LLC SFR owners, recent sales), server-side group-by-count. `deps: public API` · `reused-by: cash-buyer-ranker, jv-partner-ranker`
- **cash-buyer-ranker** — rank LLC SFR owners by recent buys + portfolio; mailing address = direct-mail channel. `deps: assessor-parcel-miner` · `reused-by: —`
- **jv-partner-ranker** — INVERTED: AZ-local, human-scale (2–40 SFR), ranked by velocity. `deps: assessor-parcel-miner` · `reused-by: —`
- **form-d-issuer-miner** — EDGAR full-text + `primary_doc.xml`, AZ; outputs offering/sold/**remaining** + principals (the "still raising" signal). `deps: EDGAR public` · `reused-by: tax-motivated-targeting, social-link-enricher`
- **dot-beneficiary-miner (gated)** — repeat Deed-of-Trust beneficiaries via paid provider / county bulk (Recorder is WAF-blocked). `deps: paid data` · `reused-by: tax-motivated-targeting`
- **skip-trace-enrichment** — entity/principal + address → BatchSkipTracing/TLO/etc. to fill blank phones. `deps: paid provider` · `reused-by: any list phone enrichment`
- **social-link-enricher** — xlsx with a verified social link per prospect; VERIFIED/PARTIAL/UNVERIFIED. `deps: business-profile-recon, lead-qualifier verification` · `reused-by: lead-qualifier output`
- **honesty-invariants** — "cash" is an unverified proxy; never fabricate phones; Maricopa-only; single-page fetch to avoid double-counting. `deps: none` · `reused-by: lead-qualifier, all list builds`
- **tax-motivated-targeting** — deadline/penalty-driven buyers (1031, cost-seg, Opportunity-Zone funds). `deps: form-d-issuer-miner, dot-beneficiary-miner` · `reused-by: motivated-buyer campaigns`

### `notion-intake-crm-cloner`
_Clones a client-OWNED leads + intake + marketing-ROI CRM into the client's own Notion workspace._
- **notion-api-db-stamper** — create every DB inside the client's workspace (they own it); API can't set status groups/formulas (human finishes). `deps: Notion token, parent page` · `reused-by: any Notion productization`
- **marketplace-shape** — two-sided case-matching build (Leads → Matches → Partners + Billing + Channels + Tasks + Staff). `deps: notion-api-db-stamper` · `reused-by: any two-sided marketplace CRM`
- **firm-shape** — single-firm intake CRM (Leads · Channels · Referral Network · Signed Cases). `deps: notion-api-db-stamper` · `reused-by: any service-firm CRM`
- **compliance-fields** — Sourcing, Consent/TCPA, Already-Represented auto-DQ, payment model, fee-agreement flag. `deps: none` · `reused-by: crm-build-standard power-dialer consent, lead CRMs`
- **intake-automation** — forms/LSA/call-tracking → Leads via API + missed-call-text-back + auto-assign. `deps: notion-api-db-stamper` · `reused-by: cf-forms capture analog`
- **marketing-roi-tuning-loop** — recurring monthly pass on which sources produce SIGNED cases → reallocate spend. `deps: none` · `reused-by: crm-build-standard intelligence, az targeting`
- **no-phi-severity-buckets** — injury stored as severity buckets, never records (out of HIPAA scope). `deps: none` · `reused-by: any regulated-data CRM`
- **solicitation-law-guardrail** — DPPA / AZ Bar 7.3 / TCPA / DNC: INBOUND leads only, never cold-solicitation. `deps: none` · `reused-by: crm-build-standard power-dialer, guardrails`
- **notion-scale-archiving** — archive closed leads (Notion slows ~10–20k rows, API ~3 req/s); huge volume → owned ingest worker is source-of-truth, Notion shows the working set. `deps: none` · `reused-by: any Notion-backed system`

## Anthropic-namespace lead/commerce skills — manifest-derived (deepen on read)
- **`custom-lead-generator`** — productized public-source lead-gen. Atoms: `lead-source-reach` (deps: profile-reach), `lead-sheet`.
- **`clover-operations-command`** — Clover POS operations command surface.
- **`cloudflare-ordering-worker`** — ordering Worker for menu/checkout.

## Solomon / verification family — anthropic-skills + solomon-verification-standard
_Governance, proof, engine-verification, release, voice._ Decompose these into atoms
(proof-runner, no-fake-PASS gate, engine-verifier, live-evidence-verifier, cloudflare-release,
readme-sync, repo-hygiene, doc-author, native-internet, voice-runtime/verification) in a later pass —
they compose the Solomon governed loop rather than client sites.

---

## Shared atoms (recur across ≥2 skills — highest-value building blocks)
The blocks below appear in multiple skills. When starting a build, reach for these FIRST — they're
the load-bearing foundations the rest compose onto.

**Data & backend spine**
- **d1-schema + migrations** — cf-identity, cf-forms, cf-functions, cf-deploy, commerce-spine, crm-build-standard.
- **method-path-router + json-response-helper + d1-access-pattern** — cf-functions primitives used by cf-forms, cf-identity, commerce-spine, crm-build-standard.
- **one-worker-serves-both** — cf-functions, under every cf build.
- **per-site-d1-node** — commerce-spine, is the data brain of crm-build-standard.

**Auth**
- **auth-middleware + users-sessions-schema + pbkdf2-password-hashing + roles** — cf-identity's core, reused by cf-forms (admin list), commerce-spine (worker-enforced roles), crm-build-standard (+ lockout/2FA hardening).
- **shared-signup-code-gate / constant-time-compare** — cf-identity → crm-build-standard invite-only, cf-forms.

**Deploy**
- **deploy-safety-gate + local-client-preview + remote-d1-create/migrations** — cf-deploy, invoked by commerce-spine & crm-build-standard provisioning.

**Money, tenancy, scale**
- **tenant-id-identity** — commerce-spine & crm-build-standard (the invariant shard-routing + R2 offload depend on).
- **money-cents + qty-milliunits** — commerce-spine & crm-build-standard commerce.
- **aes-gcm-at-rest** — commerce-spine & crm-build-standard (encrypted messaging).
- **d1-shard-overflow + r2-blob-offload** — commerce-spine, reused by crm-build-standard scale & power-dialer recordings.
- **idempotent-webhooks / append-only log** — commerce-spine (webhooks, inventory ledger) & crm-build-standard (activity + audit log).
- **free-tier-playbook** — crm-build-standard, and the discipline commerce-spine's sharding follows.

**Honesty & verification (the house discipline, everywhere)**
- **capability-readiness-probe / honest-labels** — commerce-spine's probe + crm-build-standard's "truth over spectacle" + sports' tiering-honesty-gate + lead-qualifier/az honesty-invariants: never present unverified as ready, never fake live data.
- **evidence-citation + identity-confirmation-gate + verified-output-builder** — lead-qualifier & az-cash-buyer-finder (both lean on **profile-reach** from business-profile-recon).
- **explainable / transparent-scoring** — lead-qualifier's outcome-learner & crm-build-standard's explainable-scoring: factors visible, no black box.
- **reduced-motion-lowpower-fallback** — sports-website-standard & this web-effects-catalog: same mandatory-fallback doctrine.

**Content & media (anthropic-skills web family)**
- **profile-reach** — business-profile-recon → website-build-standard, custom-lead-generator, crm, site-media-fetch, lead-qualifier, az-cash-buyer-finder.
- **self-contained-page** — website-build-standard → sports, commerce, immersive.
- **builder-edit-media / immersive-centerpiece** — website-build-standard → immersive-evidence-workspace, service-business-website, sports.
- **client-upload-flag** — site-media-fetch → builder-edit-media guided uploads.

**Compliance**
- **consent / TCPA / DNC gating** — notion-intake-crm-cloner (compliance-fields + solicitation-law-guardrail) & crm-build-standard (governed-power-dialer).

**Motion**
- **tilt** — web-effects-catalog `xv` → product cards, hero media.
- **csv-worklist-scaffold** — lead-qualifier & az-cash-buyer-finder both scaffold any-column CSV → per-lead worklist → verified xlsx.
