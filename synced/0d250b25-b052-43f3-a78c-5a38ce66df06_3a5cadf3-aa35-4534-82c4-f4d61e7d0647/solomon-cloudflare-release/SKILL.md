---
name: solomon-cloudflare-release
description: >-
  Build, validate, deploy, and troubleshoot the Solomon / TSS public site on Cloudflare
  (ronininc.org) truthfully — the Pages/Worker artifact, the apex + www domain binding, the
  no-store cache rules, and the stale-content checks. Use this whenever the ronininc.org
  production site is wrong: serving a stale Vite shell, not resolving (DNS error), out of sync
  with the validated zip, or when you are cutting a Cloudflare release from the ronininc/TSS
  repo. Trigger on "the site is stale", "ronininc.org is down / not resolving", "deploy the
  cloudflare site", "sync the public site", "release:cloudflare", "why is production serving the
  old build", or "the site doesn't match the validated zip". Deploy/promotion commands are
  side-effectful and require explicit operator approval; this skill runs read-only checks freely
  but never publishes without a yes.
---

# Solomon Cloudflare Release

The Solomon public site (ronininc.org) is a governed release artifact, not a casual deploy. It is
generated and checked by `npm run solomon:release:cloudflare` and
`npm run solomon:release:cloudflare:validate`, and its correctness rules are encoded in
`scripts/solomon-release-cloudflare-validate.mjs`. This skill's job is to keep production
truthfully in sync with the validated artifact and to diagnose the two recurring failure modes:
a **stale shell** being served, and the site **not resolving at all**. Publishing is
side-effectful — surface exactly what will happen and get an explicit operator yes first.

## Golden rules the validator already enforces (know these)

`solomon-release-cloudflare-validate.mjs` fails the release unless the deployed zip/site:

- Contains, at the top level: `index.html`, `manifest.json`, `_headers`, `_redirects`,
  `release-notes.html` — and contains **no** `.exe/.msi/.zip` payloads inside the Pages zip
  (checksum-only; installers live in GitHub releases).
- `_headers` enforces `Cache-Control: no-store` (this is what prevents stale caching).
- `_redirects` includes `/downloads`, `/public-notices`, `/documentation`.
- `manifest.json` `buildId`/`version` match `solomon-release-metadata.json`.
- `index.html` shows the required public structure (Home, Mission, Projects, Roadmap, Public
  Notices, Documentation, Downloads), the mission statement, exactly one SHA256 matching metadata,
  exactly one `.exe` href pointing at the `ronininc/solomon-releases` GitHub release, the proof
  markers `REAL_APPROVED_INTERNET_FETCH_PROVEN`, `ONLINE_VALIDATION_PROOF_PASS`,
  `EXTERNAL_PROVIDER_REASONING_CONFIG_HOLD`, and the current `buildId`.
- Must **NOT** contain: `example.com`, `Kingmaker`, the stale Vite asset `index-CH0HgECa.js`,
  or any `..._UNPROVEN` hold text. Titan may appear only as "Titan (future) … not implemented,
  not active runtime."

If a check here would fail, fix the artifact — never weaken the validator.

## Diagnosing "the site is wrong"

Work outside-in. Determine which layer is broken before touching anything.

1. **Does the domain resolve at all?** Load `https://ronininc.org` and `https://www.ronininc.org`.
   - `DNS_PROBE_FINISHED_BAD_CONFIG` / "server IP address could not be found" ⇒ **DNS/binding
     problem**, not a stale-content problem. The site isn't being served at all. Go to "Domain
     binding" below. (Observed state as of this skill's authoring: both apex and www failed to
     resolve while the account had a Worker named `ronininc` created the same day — consistent with
     a Pages→Worker migration whose custom domain wasn't attached yet.)
   - It loads ⇒ go to step 2.
2. **Is it the stale shell?** Inspect the served HTML for the validator's stale tells: presence of
   `index-CH0HgECa.js`, any `..._UNPROVEN` text, missing proof markers, or a SHA/buildId that
   doesn't match `solomon-release-metadata.json`. Any of these ⇒ production is serving an old
   deployment or a cached asset. Go to "Fixing a stale deploy".
3. **Is it a cache layer?** If the origin artifact is correct but the browser sees old content,
   confirm `_headers` shipped `Cache-Control: no-store` and purge the Cloudflare cache.

## Pages vs Worker — get the serving model straight first

The repo's release tooling talks about a Cloudflare **Pages** zip, but production may be served by
a **Worker** (there is a Worker named `ronininc` in the account). These bind custom domains
differently, and mixing them is a common cause of "nothing resolves":

- **Pages:** the project has a *Custom domain* (Pages → project → Custom domains) which creates the
  DNS records automatically; deploys publish a new version of the Pages project.
- **Worker:** the domain must be attached as a *Worker Custom Domain* (or a route), and a matching
  proxied DNS record must exist for the apex and www.

Decide which one is authoritative for ronininc.org and bind the domain to that one only. If you
migrated Pages→Worker, the old Pages custom domain and its DNS records may have been removed,
leaving the apex unbound — which produces exactly the observed DNS failure.

## Domain binding (fixing "not resolving")

This changes DNS/routing — **operator approval required** before making changes. Steps:

1. Confirm the zone `ronininc.org` is active in the Cloudflare account.
2. Bind the domain to the authoritative deployment (Pages Custom Domain, or Worker Custom Domain
   for the `ronininc` worker), for **both** apex `ronininc.org` and `www.ronininc.org`.
3. Ensure proxied DNS records exist for apex and www (Cloudflare proxy on = orange cloud).
4. Wait for propagation, then re-check resolution and re-run the validator against the live site.

> The DNS-record and custom-domain APIs are not exposed by the Cloudflare connector available in
> this environment (it surfaces Workers/D1/KV/R2 only). Do the binding in the Cloudflare dashboard,
> or connect a Cloudflare integration with DNS + Pages scope so it can be scripted. Do not attempt
> to guess or hard-code IPs.

## Fixing a stale deploy

1. Rebuild the artifact from the current source: `npm run solomon:release:cloudflare`.
2. Validate it: `npm run solomon:release:cloudflare:validate` — this must pass every golden rule
   above before you deploy. If it flags `index-CH0HgECa.js` or `_UNPROVEN` text, the source that
   generated the zip is stale; fix that, don't bypass the check.
3. Deploy the validated artifact to the authoritative target (Pages publish, or Worker deploy).
   **Side-effectful — operator approval required.**
4. Purge the Cloudflare cache for the zone so edge nodes drop the old shell.
5. Re-fetch the live site with cache bypass and re-confirm: proof markers present, no stale asset,
   SHA/buildId match metadata.

## Side-effectful commands — approval required (never run silently)

- `npm run solomon:release:cloudflare` (regenerates the artifact — usually safe, but confirm)
- Any deploy/publish to Pages or Worker, any DNS/custom-domain change, any cache purge
- `npm run solomon:release:full`, `solomon:release:build`, `solomon:release:upload-win`,
  `solomon:release:verify-win`, `solomon:promote-release`

Read-only checks (loading the site, inspecting HTML, running the `:validate` script against a local
zip) are safe to do freely.

## Reporting

State the layer and the truthful status, e.g.:
`ronininc.org: NOT RESOLVING (apex+www DNS_PROBE_FINISHED_BAD_CONFIG). Cause: domain not bound to
the 'ronininc' Worker after Pages→Worker migration. Fix: bind Worker Custom Domain for apex+www
(operator action). Artifact validator: PASSES locally.` Keep the README blocker line in sync via
`solomon-readme-sync` — it currently reads "production ronininc.org is still serving the stale
cached Vite shell"; if the real state is "not resolving," update it to the truth.
