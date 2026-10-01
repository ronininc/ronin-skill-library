---
name: comp-priced-digital-pack
description: >-
  Manufacture a passive DIGITAL product (an N-icon game-asset pack) end to end and price it from REAL
  competitor listings — the make + price half that sits in front of a digital store. Three net-new pieces:
  (1) COMP PRICING from an official marketplace API (Etsy Open API v3; nothing scraped) with a strict
  comparability filter — digital-download only, priced in USD, a readable icon count parsed from the title/
  description, a comparable size (half-to-double ours), NOT a franchise/brand listing, ≤2 per shop — then
  price = MEDIAN per-icon × our count, clamped to an optional operator floor/ceiling; too few comps → NO price,
  the line STOPS and asks (never invents one). (2) a DURABLE generation pipeline as a Cloudflare Workflow
  (image model → background removal + multi-size resize via Cloudflare Images → R2, each file hashed, the
  "done" row written LAST so a retry redoes a half-made icon) that METERS its real cost to the ledger. (3) an
  ORIGINALITY gate — subjects come from a trademark-free catalog and every prompt is refused if it names a
  franchise/brand/character/artist or "in the style of", with AI use disclosed in the listing + LICENSE.txt.
  Use WHENEVER a build must "make and sell icon/asset/clipart packs", "price a new digital product from what
  competitors charge", "generate a product catalog with AI and sell the files", "comp-based pricing with no
  sales history yet", or "a passive digital-goods line". It COMPLEMENTS digital-product-kit + commerce-spine
  (the SELL/deliver/catalog side — this is the make+price that feeds them), order-pnl-fund-gate-fulfillment
  (the fund gate still releases the file only after payment settles), sales-history-price-learning (that
  learns from your OWN sales; this prices a product that has none yet, from competitors), and runs on a
  station-engine-floor belt behind its exact-bytes gate. Guardrail: nothing is listed until the operator
  approves the EXACT pack + price (every file hash, the listing, the price and its evidence); no price is ever
  invented; originality is checked before any prompt reaches the model; AI use is disclosed.
---

# Comp-Priced Digital Pack (make it, price it from real comps, deliver it)

## What it is / when to use
The manufacturing + pricing engine for a passive digital product. It generates the goods durably, prices them
from real competitor listings on an official marketplace API (never invented, never scraped), gates originality
before any prompt runs, meters its real cost truthfully, and parks the finished pack at an exact-bytes review
before anything is listed. The selling/delivery/catalog lives in the commerce skills; this is the half that
makes the product and decides its price.

Use it to produce and price icon/asset/clipart packs (or any generatable digital bundle), especially when
there's no sales history yet so price has to come from competitors. Compose with `digital-product-kit` +
`commerce-spine` (sell/deliver), `order-pnl-fund-gate-fulfillment` (fund gate), `sales-history-price-learning`
(later, once you have your own sales), and run it on a `station-engine-floor` belt.

## Reference implementation (exact)
- Comp pricing from the official API: `worker/station/pack-comps.ts:77` `evaluateComps()` (pure filter +
  median-per-icon × target, floor/ceiling clamp), icon-count parser `:45` `parseIconCount()` (reads "48 icons",
  "set of 45"; ignores "300 DPI"/"1024x1024"), live fetch `:129` `fetchComps()` (Etsy `listings/active`,
  `x-api-key` from `ETSY_API_KEY`, `MIN_COMPS=5`, offline stub via `STATION_COMPS_STUB`), evidence saved
  `:155` `saveComps()`. The brand/franchise exclusion regex `:24`.
- The belt (demand → brief+price → make → review gate → list → sell): stages
  `worker/station/asset-packs.ts:491` `assetPackStages`; demand ranks OWN store sales first, else least-made
  theme `:100`; brief prices from comps or operator, else BLOCKS `:146` (`:161` "the belt never invents a price").
- Durable generation Workflow: `worker/station/pack-maker.ts:16` `PackMakerWorkflow` (batches of `MAKE_BATCH`,
  retries, calls `advance()` when done); one icon all sizes, done-row LAST `worker/station/asset-packs.ts:212`
  `makeIcon()`; batch step re-checks kill switch + desk/gear `:279` `makeIconBatch()`; plan purges stale takes
  `:261` `planMake()`.
- Image model + Cloudflare Images transform: `worker/station/asset-packs.ts:191` `generateImage()`, `:201`
  `imagesTransform()` (`segment:'foreground'` background removal + resize); honest output degrade (no IMAGES
  binding → 1024 JPEG on a solid bg, not transparent) `:48` `packOutput()`.
- Metered cost → ledger (list price, rounded UP, one line per paid service per make): `:306` `bookMakeCost()`.
- Originality gate: `worker/station/asset-packs.ts:62` `BLOCKLIST` + `:63` `originalityProblem()`, enforced on
  every prompt in the brief `:155`; the license + AI disclosure `:72` `PACK_LICENSE`.
- The approved MANIFEST (what the operator's hash binds): `worker/station/asset-packs.ts:360` (title,
  description, price + basis, license sha, every file hash) → saved as a `pack` artifact.
- Delivery/sell (revenue line only when paid+funded, refund reverses + revokes): `:448` `syncPackSales()`,
  streamed ZIP `:532` `serveDownload()`. Operator reprice at the gate voids the approval `:400` `setPackPrice()`.
- The trademark-free catalog + manual fallback band: `worker/station/pack-catalog.ts:13` `THEMES`, `:126`
  `MANUAL_BAND`. Wiring: Workflow exported `worker/index.ts:88`; public preview/download routes `:76`.
  Migrations `0151_station_asset_packs.sql`, `0155_station_pack_comps.sql`.

## How to reapply
1. **Price from an OFFICIAL API, purely and defensibly.** Keep `evaluateComps(listings, target, {floor,ceiling})`
   pure. A comp counts ONLY if: digital download, priced in USD (the API's own conversion allowed but flagged),
   a readable unit count, a comparable size (ceil(target/2)…target×2), not a franchise/brand listing, and ≤N per
   shop. Price = median per-unit × target, clamped. Under `MIN_COMPS` comparable listings → return `ok:false`
   with a reason; the belt BLOCKS and asks the operator for a price. Save every listing seen (used or not, and
   why) as the price EVIDENCE. Never scrape; a source without a public search API is shown as manual context only.
2. **Generate durably as a Workflow, not inside the click.** A pack is dozens of generations + hundreds of
   transforms — minutes of work. Run it as `WorkflowEntrypoint` in batches with retries; write each icon's
   "done" row LAST so a retried step redoes a half-made icon instead of shipping it; re-check the kill switch and
   the desk/gear each batch; when the last file lands, call `advance()` so the pack walks itself to review.
3. **THE INVARIANT — originality before the model, price from evidence, nothing lists without an exact-bytes
   approval.** Subjects come from a trademark-free catalog; every prompt is refused if it hits the brand/style
   blocklist. The price is comps or the operator's number for THIS pack — never invented. The operator approves
   the exact MANIFEST (every file hash, the listing text, the price + its basis, the license sha); repricing at
   the gate re-saves the artifacts and VOIDS any prior approval. AI use is disclosed in the listing and LICENSE.txt.
4. **Meter the real cost to the ledger**, rounded UP, one line per paid service (image gen; transforms), from
   the metered call counters — never estimated (see `truthful-money-ledger`).
5. **Degrade honestly.** Without the background-removal binding, produce a solid-background JPEG and SAY the
   listing is not transparent — the listing must state the real format.

## Gotchas (from the code)
- **The icon-count parser is where comparability lives or dies** — it must read "48 icons"/"set of 45" but
  reject dimensions ("300 DPI", "1024 x 1024") and units, or a resolution gets priced as a quantity
  (`pack-comps.ts:41-63`). Keep the NOUN/UNIT/GROUP token rules.
- **No comps is a STOP, not a guess.** The brief blocks with the comps reason + a manual band for context; the
  belt waits for the operator to set a price (`asset-packs.ts:161`). A one-click "use the suggestion" is fine;
  an auto-invented price is not.
- **The "done" row is the make's commit.** Writing the asset row last (after R2 puts + per-size file rows) makes
  a Workflow retry idempotent; `planMake()` purges files from a superseded `make_key` (R2 + rows) so a changed
  brief never ships stale icons (`asset-packs.ts:210-212,261`).
- **Keep `asset-packs.ts` off the `cloudflare:workers` path** — the store/commerce code imports it, so the
  Workflow lives in `pack-maker.ts` and `pack-comps.ts` uses the shared `safeFetch`/egress guard (`:11,139`).
- **Only preview images are public; the rest are paid-only**, downloads are token-gated with an expiry + max-use
  claim, and a refund revokes the grant and reverses the ledger line (`asset-packs.ts:38,465,540`).
- **Validated** by the `STATION_COMPS_STUB`/`STATION_IMAGE_STUB` offline proofs (Etsy-shaped responses +
  deterministic images so the real filter/pricing/metering run without network) and commit
  "Station asset packs: competitive 48-icon transparent packs, priced from real comps (#54)".
