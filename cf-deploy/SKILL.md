---
name: cf-deploy
description: >
  Preview a site/app the way a client will see it, and put it live on a real
  URL — a clone of Netlify Deploy Previews + Netlify hosting, built on Cloudflare
  (wrangler dev for local preview, wrangler deploy / Pages for production, D1 for
  the database). Use whenever the task is "let me see it as a client would",
  "get a preview link", "put it online", "deploy this", "go live", "ship it to
  Cloudflare", "set up the database in production", or "give me a URL to share".
  Covers running a client-viewable local server, creating a remote D1 and
  applying migrations, deploying the Worker, custom domains, and the safety rule
  that any real deploy needs the operator's explicit go-ahead.
---

# cf-deploy — preview like a client, then go live (Netlify Deploy Previews, cloned)

Two jobs Netlify does for you, reproduced on Cloudflare:
1. **See it as a client will** — a live, clickable preview.
2. **Put it on a real URL** — production hosting + database.

## Job 1 — client-viewable preview (no account, no cost, safe to run)
From the app folder:
```bash
npm run db:init          # wrangler d1 migrations apply <db> --local
npm run dev              # wrangler dev --port 8811   (serves the whole app locally)
```
Then open the preview and drive it: `preview_start {url:"http://localhost:8811"}`,
`read_page`, `computer` (click/type), `read_console_messages`. Take a screenshot
so the operator sees exactly what a client sees. This is the default way to show
work — always prefer a real running preview over describing it.

## Job 2 — go live (SIDE-EFFECTFUL — get an explicit "yes" first)
Publishing puts content on the public internet under the operator's Cloudflare
account. Confirm before running any step below.

1. **Create the remote database** and copy its id into `wrangler.jsonc`:
   ```bash
   wrangler d1 create <db-name>          # prints database_id
   ```
2. **Apply the schema to production:**
   ```bash
   wrangler d1 migrations apply <db-name> --remote
   ```
3. **Set secrets** (never commit them):
   ```bash
   wrangler secret put TEAM_CODE          # and any API keys
   ```
4. **Deploy the Worker (serves API + static assets in one):**
   ```bash
   wrangler deploy
   ```
   → live at `https://<name>.<subdomain>.workers.dev`.
5. **Custom domain:** add a route in the dashboard or `wrangler.jsonc`
   (`routes`/`custom_domain`), then bind the DNS record. (See the project's
   Cloudflare release skill for the apex+www binding pattern.)

## Static-only sites (no backend)
Use Cloudflare Pages instead of a Worker: `wrangler pages deploy ./public
--project-name <name>`. Adds preview URLs per deploy — the closest match to
Netlify Deploy Previews.

## The MCP path (when the Cloudflare account is connected)
If Cloudflare MCP tools are authorized this session, `d1_database_create`,
`d1_database_query`, and the Workers tools can do the same without the CLI — but
they hit the operator's real account, so the same "confirm first" rule applies.

## Safety
- Local preview (Job 1): run freely.
- Remote create/deploy/secret (Job 2): **ask first every time.** Report the exact
  URL after it's live; verify the live site actually serves the new build (don't
  trust a green deploy log alone).

Pairs with **cf-functions**, **cf-identity**, **cf-forms**, and the `wrangler`
skill for command details.
