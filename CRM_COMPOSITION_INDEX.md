# Ronin Skill Composition Index

_The mix-and-match map: pick a recipe → get the skill stack + build order. Grows automatically via the `skill-harvest` skill. Current library: **145 skills** (2026-09-19)._

## Foundation — almost every build starts here
`cf-identity` → `cf-abuse-guard` → `clearance-rbac` (auth + roles) · `d1-migration-recipes` + `d1-proof-harness` (schema + proof) · `feature-activation-gate` + `append-only-audit-log` (monetization switch + trail) · `vanilla-spa-shell` + `portal-design-system` (UI) · `cf-deploy` (ship) · `video-walkthrough` (deliver the demo).
_Harden it:_ `two-keystore-password-integrity` (tamper-evident hashes + session-epoch logout) · `last-usable-owner-guard` (never lock out the last admin) · `totp-mfa` + `scoped-bearer-token` · `field-encryption-at-rest` (PII columns) · `idempotent-public-submission` (public POSTs).

---

## Recipes (pick one, add packs)

### 1 · Local-business site + CRM  *(restaurant, salon, shop, contractor)*
`website-build-standard` → `local-seo-location-pages` (a page per location/city when multi-site) → `commerce-spine` → `d1-image-store` (free-tier product photos) → `crm-build-standard` → `cf-forms` (capture) → `quick-capture-inbox` (jot leads/photos from the phone) → `governed-email-outreach` + `outbound-compliance-gate` → `self-schedule-booking` (bookings) → `geo-directory-prospecting` (fill the pipeline) → `white-label-branding` → `cf-deploy` → `video-walkthrough`.

### 2 · Lead-gen / appointment-setting engine  *(Ronin lead engine, Wavelygth dialer)*
`crm-build-standard` (dialer + scoring ML) → `d1-work-queue` + `attack-list-priority-queue` (claim + priority) → `hfp-dialer-companion` + `device-presence-gate` (own-phone dialing) → dialer pack: `predictive-dialer-pacing` (FTC-safe over-dial) + `local-presence-did-pool` + `pluggable-voice-carrier` → compliance: `outbound-compliance-gate` + `tcpa-consent-capture` → source: `geo-directory-prospecting` + `open-data-signal-discovery` + `github-lead-mining` + `meta-lead-ads-connector` (inbound lead ads) → enrich: `contact-enrichment-deliverability` + `decision-maker-email-extractor` → score/fit: `lead-qualifier` + `sovereign-edge-scorer` → reach: `governed-email-outreach` + `text-campaign-platform` + `send-once-idempotent-email` → paywall/sell the lead: `feature-activation-gate` + `lead-marketplace-auto-match` + `exclusive-lead-claim-desk` → `rotating-leadgen-scheduler` (cadence).

### 3 · Agency / services CRM
`crm-build-standard` → `opportunity-markets-bid-desk` (inbound RFPs) → `services-delivery-lifecycle` (projects/retainers) → `crew-job-scheduler` (dispatch the work) → `crm-workforce-productivity` (who's actually working) → invoicing: `service-invoice-ledger` + `printable-invoice-document` + `wire-payment-collect-reconcile` → `content-studio-publisher` + `auto-blog-network` (marketing) → `self-schedule-booking` → `partner-referral-program` → operator layer: `governed-operator-console` + `crm-mcp-server` + `private-operator-companion-pwa`.

### 4 · Investor / fund portal  *(Wavelygth)*
`cf-identity` → `clearance-rbac` → `d1-tenancy-wall` (isolation) → `fail-closed-onboarding-gate` (KYC/AML) → `valuation-pof-engine` (proof-of-funds) → dashboard: `portal-design-system` + `vanilla-spa-shell` + `vanilla-svg-charts` → `governed-email-outreach` → `crm-build-standard` dialer → `cinematic-evidence-walkthrough` (the tour).

### 5 · Dropship / e-commerce store
`commerce-spine` → `order-pnl-fund-gate-fulfillment` (per-order P&L + fund-gate) → find winners: `dropship-opportunity-scorer` + `cj-dropshipping-connector` → products: `mystery-box-balancer` + `digital-product-kit` → images: `d1-image-store` (free tier) → loyalty/price: `member-spend-unlock` + `sales-history-price-learning` + `prepaid-wallet-ledger` → docs: `printable-invoice-document` → trust: `risk-classified-review-queue` → safety: `capital-leak-breaker` + `money-feed-health-monitor` + `dormant-event-alert-router` (alerts) → `shopify-order-bridge` (import) → `installment-financing-intent` → `content-studio-publisher` → `white-label-branding`.

### 6 · Team / crew portal  *(field teams, sales floor, dispatch)*
`cf-identity` → `clearance-rbac` + `last-usable-owner-guard` → `crew-job-scheduler` (jobs) → `team-messaging-board` (comms) → `crm-workforce-productivity` (real-time who's-working, activity-derived) → `device-presence-gate` → `private-operator-companion-pwa` (the phone command app) → `dormant-event-alert-router` (page the operator).

---

## Add-on packs — bolt onto any recipe
- **Autopilot & governance:** `pipeline-autopilot` + `graduated-autonomy-tiers` + `reply-intent-triage` + `governed-operator-console` + `crm-mcp-server` + `governance-diode` + `append-only-audit-log` + `non-blocking-dissent-record` + `contribution-credit-canon`.
- **Sovereign intelligence (zero-egress ML):** `sovereign-edge-scorer` (0/1 propensity) + `segment-shrinkage-estimator` (numeric estimate) + `ledger-demand-forecast` (time-series demand) + `blended-score-trust-gate` (fuse + gate) + `vectorize-semantic-layer` (semantic search) + `reference-intel-matcher` (match).
- **Content & social growth:** `content-studio-publisher` + `auto-blog-network` + `pluggable-publisher-backend` + `pluggable-draft-brain` + `social-dm-inbox` + `dormant-reactivation`.
- **Operator surfaces:** `governed-operator-console` + `private-operator-companion-pwa` + `crm-workforce-productivity` + `dormant-event-alert-router` + `team-messaging-board` + `quick-capture-inbox`.
- **Data intake:** `agnostic-import-parser` + `chunked-uploader` + `data-feed-intake` + `admin-search-export` + `single-source-data-embed`.
- **Storage / media:** `worker-media-headers` + `chunked-uploader` + `d1-image-store` (free-tier images in D1).
- **Immersive / 3D web:** `web-effects-catalog` + `resilient-hero-video-sequence` + `scroll-scrub-video` + `webgl-product-turntable-studio` + `gltf-draco-model-normalizer` + `parametric-3d-model-builder`.
- **Local SEO reach:** `local-seo-location-pages` (a page per location/city) + `website-need-scorer` (prospect scoring).
- **Real-estate deal desk:** `confirmed-inputs-decision-gate` + `buy-box-matcher` + `az-cash-buyer-finder` + `valuation-pof-engine`.
- **Telephony:** `predictive-dialer-pacing` + `local-presence-did-pool` + `pluggable-voice-carrier` + `hfp-dialer-companion` + `device-presence-gate`.
- **MFA / hardening:** `totp-mfa` + `scoped-bearer-token` + `signed-webhook-intake` + `two-keystore-password-integrity` + `last-usable-owner-guard` + `field-encryption-at-rest` + `idempotent-public-submission`.
- **Federation / multi-node:** `federation-inbound-sandbox` + `non-blocking-dissent-record` + `contribution-credit-canon`.
- **Site families:** `sports-website-standard` + `clover-connector` (POS) + `shopify-order-bridge`.
- **Connector hardening (outbound):** `ssrf-safe-egress-transport` (safe fetch of an attacker-influenced URL) + `connector-egress-circuit-breaker` (total timeout + trip on a flapping provider) — wrap any `clover-connector` / `google-oauth-connector` / `cj-dropshipping-connector` / remote fetch; pairs with `signed-webhook-intake` (inbound).
- **Knowledge & memory:** `sqlite-fts5-knowledge-base` (offline lexical/FTS5 search) + `vectorize-semantic-layer` (semantic embeddings) + `fact-preference-memory` (learned-vs-stated preferences) + `data-feed-intake`.
- **AI plumbing:** `local-first-inference-ladder` (local→overflow→premium, egress-gated) + `pluggable-draft-brain` (draft try-order) + `pluggable-publisher-backend`.
- **Prompt→app generation:** `spec-contract-scaffold-pipeline` (spec-as-contract + deterministic floor) + `collision-safe-identifier-derivation` (safe DB keys from names) + `untrusted-preview-sandbox` (render the generated artifact safely) + `pluggable-draft-brain`.
- **Deliverables / output:** `drive-rich-doc-generator` (HTML→Google Doc, CSV→formula Sheet) + `printable-invoice-document` + `cinematic-evidence-walkthrough` + `video-walkthrough`.
- **Localization:** `universal-i18n-runtime` (detect + swap strings, any language, RTL) + `spanish-regional-localization` (regional copy style).
- **Creative media (generate + finish):** `svg-marketing-asset-generator` (intent → SVG poster/logo/flyer) + `media-generation-dispatch` (parse intent → swappable cloud-gen engine) + `webgpu-image-finish-pass` (in-browser cinematic grade/filter) + `vanilla-svg-charts`.
- **Geo & mapping:** `overpass-query-hardening` (safe OSM Overpass calls) + `offline-osm-basemap-map` (dark branded OSM map, no paid SDK) + `osm-building-massing-layer` (real 3D building footprints) + `geospatial-scene-projector` (GeoJSON → engine-agnostic 3D scene) + `geo-directory-prospecting` (POI leads).
- **Agent tool safety:** `governed-mcp-tool-actuator` (safely let an agent drive an external MCP/tool server — verb-classified, confirm-gated) — the client-side inverse of `crm-mcp-server`.

---

## Build order (any recipe)
1. **Foundation** — auth + schema + proof harness (+ hardening pack for anything with admin roles or PII).
2. **Spine** — the core CRM / commerce node.
3. **Engines** — the recipe-specific pieces.
4. **Outreach + compliance** — always behind `outbound-compliance-gate` (+ `tcpa-consent-capture` for phone).
5. **Add-on packs.**
6. **Branding + deploy + walkthrough.**
7. **`skill-harvest`** — run it at the end; any net-new capability re-enters the library and this index.

## How this grows
Never hand-maintained. `skill-harvest` (run at the end of a build or across the portfolio) adds new skills; regenerate this index to slot them into the recipes above. The 2026-09-19 portfolio sweep added **44 net-new skills** (library 82 → 126) from the novel repos — SLIK team portal, Pineapple/Clover + the sovereign edge-ML kit, Case Plug's lead marketplace + telephony, supercar's 3D configurator, Kingmaker/jv federation + oversight, and oro-cloud dropship — while gap-scans of Wavelygth and ronininc found little new and the thin client-site repos were confirmed instances of `website-build-standard` + `commerce-spine`. Several new skills ship disconnected/spec-stage in their source (flagged in each SKILL.md with the wiring they need). The 2026-09-19 **targeted** pass on the private TSS/Solomon repo then added **10 client-reusable plumbing skills** (126 → 137) — SSRF-safe egress + circuit breaker, the local-first inference ladder, the SQLite-FTS5 knowledge base + fact/preference memory, the Drive rich-doc generator, the universal i18n runtime, and the prompt→app trio (spec-contract pipeline + collision-safe IDs + untrusted-preview sandbox) — all genericized, with the Solomon moat (governance / OSIRIS / Kingmaker / voice-identity / self-hardening immune) and vendored `.solomon-upstreams` explicitly excluded. A second targeted TSS pass then added **8 more** (137 → 145) from the media/geo/desktop subsystems — SVG marketing-asset generator, pluggable media-generation dispatch, WebGPU image-finish, the OSM/Overpass geo trio (query-hardening + offline basemap + 3D building massing) + geospatial-scene projector, and the governed external-MCP tool actuator — again excluding the moat, the orb/evidence product surface, the local 8GB generative-media runtime, and vendored Cesium/ghost-os/vgpu.
