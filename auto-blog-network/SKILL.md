---
name: auto-blog-network
description: >-
  A registry of independent, self-running niche SEO blogs hosted on ONE Cloudflare Worker + D1 and
  path-routed at /blog/<blog>/<post>: a daily per-blog cron picks the next topic, generates a
  ~700-word article via Cloudflare Workers AI (near-zero cost), sanitizes the HTML, and publishes it
  server-side as a fully SEO'd page (title/description/canonical/OG + optional AdSense + affiliate
  disclosure + view counting). Use WHENEVER a client/build wants "a self-running blog", "auto-generate
  SEO content", "an AdSense/affiliate content site", "spin up multiple niche blogs cheaply", "a
  content engine that feeds leads", "programmatic SEO", or "run many blogs from one Worker". Each row
  in the `blogs` table is a fully independent blog (its own niche, topics, schedule, AdSense id) — run
  dozens for pennies. COMPLEMENTS website-build-standard (this is the traffic/SEO organ that bolts a
  blog network onto a site; it does NOT build the marketing site) and pluggable-draft-brain (the
  reference calls Workers AI DIRECTLY via env.AI — swap in draft-brain if you want Claude/OpenAI/
  self-hosted authorship with fallback). Feeds leads into a crm-build-standard CRM via the on-page CTA.
  Guardrails: ships DISABLED per blog (enabled=0), an at-most-once daily claim prevents duplicate runs
  under overlapping cron ticks, a quality floor rejects thin/empty output, generated HTML is sanitized
  (no script/style/iframe/on*-handlers/javascript:), and the AI prompt forbids invented stats/quotes.
---
# Auto-Blog Network — many self-running SEO blogs on one Worker + D1

One Worker + D1 hosts a *registry* of independent blogs. Each `blogs` row is its own journal — niche,
topic rotation, posting schedule, AdSense id, affiliate disclosure. A daily cron loops every enabled
blog, writes the day's article(s) with Cloudflare Workers AI, sanitizes and publishes them, and
serves each post as an SEO'd HTML page at `/blog/<slug>/<post-slug>`. Near-zero marginal cost, so a
client can run a whole network as a monetizable, lead-feeding traffic asset.

**When to use:** a client wants ongoing SEO content / an AdSense-or-affiliate content play / many
niche blogs without a CMS or per-article writing cost. **What it composes with:**
`website-build-standard` (the site this attaches a blog network to), `pluggable-draft-brain`
(optional: better authorship models with fallback), and `crm-build-standard` (the CTA funnels
readers into the CRM as leads).

## Reference implementation (ronininc-site — OPEN these)
- **`worker/blog.ts:1-289`** — the whole engine:
  - Helpers: `slugSeg`/`postSlug` (14,25-27), `sanitize` (28-33 — strips
    script/style/iframe/object/embed/link/meta + `on*` handlers + `javascript:`, caps 60 KB),
    `parseTopics` (22-24).
  - Registry: `listBlogs` (37-40), `getBlogBySlug` (41-43), `createBlog` (45-60 — unique-slug loop),
    `storePost` (62-68).
  - Generation: `generateArticle` (72-100 — Workers AI call, strict `TITLE:/EXCERPT:/BODY:` parse,
    quality floor: returns null if no title or body < 200 chars).
  - Daily cron: `runDailyBlog` (104-110 — loops enabled blogs, per-blog guarded) and `runBlogDaily`
    (111-127 — the at-most-once daily claim + topic-cursor rotation, ≤5 posts/day).
  - Admin: `blogDashboard` (131-147), `saveBlogSettings` (149-166 — create-or-update),
    `applyBlogFields` (168-185), `generatePostNow` (187-200 — manual generate),
    `updateBlogPost` (202-218 — edit/publish/archive/delete).
  - Public rendering: `BLOG_HEADERS` (222-233 — AdSense-friendly CSP), `shell` (235-261 — full SEO
    head), `blogDirectoryPage` (263-268), `blogIndexPage` (270-277), `blogPostPage` (279-288 — renders
    + increments `views`).
- **`migrations/0026_blog.sql`** — the original single-blog schema (`blog_settings` + `blog_posts`).
- **`migrations/0027_ventures_multiblog.sql`** — the multi-instance upgrade: the `blogs` registry
  table, carrying the single 0026 blog forward as the first instance, and `blog_posts.blog_id`.
- **`worker/index.ts:133-141`** — the public routes: `/blog` (directory), `/blog/<slug>` (index),
  `/blog/<slug>/<post>` (post), served OUTSIDE the strict app security headers so the AdSense CSP
  from `BLOG_HEADERS` applies.
- **`worker/index.ts:210-214`** — cron wiring: `runDailyBlog(env)` in `scheduled()`, `.catch()`-guarded.
- **`worker/admin.ts:346-349`** — gated admin routes (`blog`, `blog/settings`, `blog/generate`,
  `blog/post`).
- **`public/admin/admin.js:1732-1822`** — the admin UI (blog list, per-blog settings, post table).

## How to reapply it into a client build
1. **Migrations.** Apply `0026` then `0027` (renumber). If the client only ever wants ONE blog you
   can still use the `blogs` registry — just create a single row.
2. **AI binding.** Add `"ai": { "binding": "AI" }` to `wrangler.jsonc`. Without it, generation is a
   no-op locally (`generatePostNow` returns 503) — Workers AI only runs on a deployed Worker. Default
   model `@cf/meta/llama-3.1-8b-instruct`; override per-blog via the `model` column.
3. **Handlers.** Drop in `worker/blog.ts`. Rebrand the hardcoded brand strings in `shell` (256-260 —
   the CTA copy, footer, "→" link) to the client's brand; make them env/settings-driven if reused
   across clients. Point the CTA link at the client's own conversion page.
4. **Public routes.** Wire `index.ts:133-141` BEFORE the static asset fall-through and OUTSIDE
   `withSecurity` (the blog sets its own AdSense-permitting CSP). Add `/blog*` to
   `run_worker_first` in `wrangler.jsonc`.
5. **Cron.** Ensure a cron trigger exists and call `runDailyBlog(env)` from `scheduled()`,
   `.catch()`-guarded (`index.ts:210-214`). It runs at each blog's local `daily_hour`.
6. **Admin routes + UI.** Add `admin.ts:346-349` behind your staff gate; port or rebuild the UI.
7. **Per-blog config.** Operator sets: title/tagline, timezone, `daily_hour`, `posts_per_day` (1-5),
   the topic list (rotated by `topic_cursor`), model, `adsense_client` (e.g. `ca-pub-…`), affiliate
   disclosure, and flips `enabled`.

## Gotchas (from the code)
- **Ships disabled; the at-most-once claim is load-bearing.** `runBlogDaily` claims the day with
  `UPDATE blogs SET last_run_day=? WHERE id=? AND (last_run_day IS NULL OR last_run_day<>?)` and bails
  if `changes==0` (118-119). This is what stops overlapping cron ticks from generating the same day's
  posts twice — keep it; don't replace it with a read-then-write check.
- **Workers AI is deploy-only.** `env.AI` is undefined in local miniflare without the binding, so
  generation returns null / 503. Test generation against a deployed preview, not `wrangler dev`.
- **Quality floor + strict parse.** `generateArticle` requires the model to return the exact
  `TITLE:/EXCERPT:/BODY:` shape and rejects output with no title or a body under 200 chars (returns
  null → no post stored). A weaker/renamed model may fail the parse and silently produce nothing —
  check the `blog_generate_error` logs.
- **All generated HTML is sanitized** (`sanitize`, 28-33) AND re-sanitized on manual edit
  (`updateBlogPost`, 212). The model is told to emit only `<h2><p><ul><li><strong><em>`; anything
  else (scripts, iframes, inline handlers, `javascript:`) is stripped. Don't loosen this — it's the
  guard against a prompt-injected or malformed article shipping active content.
- **Blog pages are intentionally OUTSIDE the strict app CSP.** They set their own
  AdSense/GoogleSyndication-permitting CSP in `BLOG_HEADERS`. If you route them through your app's
  `withSecurity`, AdSense breaks. Keep them on the dedicated header path.
- **The prompt forbids invented stats/quotes** (75, 84) — this is an honesty guardrail, not
  decoration. Preserve it; auto-generated content that fabricates data is a liability for the client.
- **Slugs are unique + collision-handled** (`createBlog` loop, `postSlug` appends a random suffix).
  Post slug is `title-slug + '-' + random`, so two posts with the same title don't collide.
- **`posts_per_day` is hard-capped at 5** (`Math.min(b.posts_per_day, 5)`, 121) even if the column
  says more — a guard against a runaway generation loop.
