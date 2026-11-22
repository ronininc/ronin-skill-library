---
name: scripture-armor-worker-integration
description: >-
  Port Scripture Armor source-review rules into an authenticated Cloudflare Worker service and verify its request boundaries. Use when adding an on-demand Armor code scanner to a web application; complements scripture-armor-build, not a WAF, runtime exploit blocker, or full native Armor replacement.
---

# Scripture Armor Worker Integration

## Scope
Offer an on-demand source review endpoint using a pinned Armor ruleset, with supplementary syntax-aware JavaScript checks. Source is data: do not execute, import, fetch URLs from, persist, log, or return source excerpts. A clean result means no covered finding was detected, not that the program is secure. Do not describe this as the full native product, a pentest completion, or permanent immunity.

## Inputs and provenance
Identify the authorized application, deployment account, canonical origin, human-session resolver, eligible roles, rulepack version/hash, supported syntax, and existing storage/bindings. Reuse the application's trusted session mechanism; never create a production test bearer. Preserve customer-specific code and evidence outside this reusable library. Verify upstream redistribution rights before bundling rules.

## Implementation contract
- Mount a single explicit POST route, for example `/api/armor/scan`, only at its configured canonical origin. Do not trust forwarded Host or a caller-provided origin as configuration.
- Require an authenticated eligible human with completed sign-in. Deny agent bearer authorization even when accompanied by a human cookie. Require same-origin Origin; reject unsupported method/content type and malformed input.
- Accept a source string and optional logical filename. Treat filename as a label, not a filesystem path. Bound UTF-8 source bytes (reference adapter: 1 MiB) and streaming request bytes independently; never trust Content-Length alone.
- Apply atomic durable rate budgets across Worker instances. Reference defaults: 30 anonymous requests/minute shared, 60 per authenticated user/minute. These are configurable policy, not universal capacity guarantees. Hash user IDs for budget keys. Store only budget metadata, not submitted code. Budget/auth backend failure must refuse the scan.
- Return non-cacheable structured findings, explicit scope and review-required state. Parsing failure or analysis-budget exhaustion cannot yield a clean verdict.
- For JS, syntax analysis may distinguish direct regex-literal `.exec` from executable calls and detect constant computed global eval/Function calls. Do not broadly suppress every `.exec`, decode and execute code, or claim complete semantic analysis. Unsupported TS/JSX needs review or an explicitly supported parser.

## Evidence gate
1. Compare native and ported rules against identical source fixtures; record exclusions, size/syntax limits and false positives. Pin the actual rulepack and parser versions.
2. Test benign regex use, dangerous direct/computed execution, mixed safe/unsafe calls on a line, malformed JS, Unicode/escaped JSON and byte limits. Include negative controls; format/schema tests alone do not prove detection.
3. Exercise the actual Worker runtime, not only mocks: anonymous/ordinary-user/agent/owner/tech combinations, bearer plus valid cookie, hostile/missing Origin, wrong canonical host, unsupported methods, bad cookies, oversized streaming bodies and dependency failure.
4. Test rate controls concurrently across isolated instances against the real local storage engine; verify the threshold and reset, not merely a mocked counter.
5. Run the app regression suite. Perform authorized, bounded adversarial tests with the owner's available tools against an isolated test deployment. Record tool versions, target scope, commands, findings and retests. Never attack unrelated hosts.
6. Deploy only within authorization, preserving all existing Worker bindings/secrets/routes and applying only reviewed necessary migrations. Keep previous version and rollback instructions.
7. Verify exact live version and anonymous rejection. Separately exercise a real authorized production scan using an existing approved session and harmless fixture. If that is not done, say explicitly: authenticated production scanning NOT VERIFIED. Do not equate successful deployment or local auth mocks with this check.

## Reusable service delivery
Provide the integration, bounded attack/test evidence, findings/remediation register, operating limits and rollback runbook. Offer custom-scoped integration/review via consultation when pricing is unset. Keep client deployments, identities, proprietary source and raw attack data out of public marketing and this library. Separate evidence for source review, access controls and runtime protection; one does not establish the others.

## Reference verification boundary
The initial 2026-11-16 Worker integration passed scoped local checks and was deployed. At minting, authenticated production scanning was not exercised. This historical status is not certification of another deployment; rerun the gate for each release.
