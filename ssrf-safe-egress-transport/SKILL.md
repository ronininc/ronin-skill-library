---
name: ssrf-safe-egress-transport
description: >-
  A hardened outbound-HTTP transport for a SERVER/Node backend (with a documented Cloudflare Worker
  degradation) that fetches an attacker-influenceable URL SAFELY. Resolve the hostname yourself,
  classify the RESOLVED IP and refuse anything that is not PUBLIC (loopback / private / link-local /
  cloud-metadata 169.254.169.254 / CGNAT / reserved — across every IPv4 and IPv6 encoding, including
  ::ffff: IPv4-mapped, 6to4, IPv4-compatible, and decimal/hex/octal literals), then PIN the socket to
  that exact validated IP via a custom lookup so a DNS-rebind cannot swing it to localhost after the
  check. Re-validate on EVERY redirect hop, refuse https→http downgrades and credentialed cross-origin
  redirects (never forward a bearer/API-key to a host the remote server named), and enforce a
  TOTAL-deadline timeout (not just Node's inactivity timer), a byte cap + identity encoding
  (decompression-bomb defence), a partial-body guard, and a host-bound bearer that never leaves for an
  un-enrolled host. Use WHENEVER a build fetches a URL it does not fully control from the backend —
  "fetch this URL / feed / sitemap", "server-side link preview / unfurl", "validate or preview a webhook
  or callback URL the user typed", "import from a remote endpoint", "call a provider REST API from Node",
  "proxy an outbound request", or ANY SSRF-exposed server fetch. COMPLEMENTS signed-webhook-intake (that
  hardens what you ACCEPT inbound; this hardens what you SEND / fetch outbound) and carries a credential
  minted by scoped-bearer-token or obtained via google-oauth-connector without leaking it across origins.
---

# SSRF-Safe Egress Transport

## What it is / when to use
A drop-in replacement for `fetch()` on the server whenever the URL is even partly caller-influenced
(typed by a user, read from a page you were told to crawl, taken from a webhook/callback field, or
returned by a search). A naive `fetch()` will happily connect to `127.0.0.1`, `169.254.169.254`, or a
private-network host, turning your backend into a probe of its own internals (Server-Side Request
Forgery). String-blocklisting hostnames does not work — `localhost`, `0x7f000001`, `2130706433`,
`0177.0.0.1`, `::ffff:127.0.0.1`, and an attacker-owned domain whose A-record points at loopback all
reach the same place. This transport defeats every one of those by judging the **resolved IP** and
**pinning** the socket to it.

Reach for it when a build has ANY of: a "fetch this URL" feature, a server-side link/preview unfurler, a
step that validates or previews a user-supplied webhook/callback URL, a remote-feed importer, or a Node
backend calling a third-party REST API with a bearer. Do NOT reach for it for a purely static
same-origin call to a hardcoded, trusted host with no credential — plain `fetch` is fine there.

## What it composes with
- **signed-webhook-intake** — the mirror image: that verifies what arrives INBOUND; this hardens what
  leaves OUTBOUND. A CRM that both receives provider webhooks and fetches remote data uses both.
- **scoped-bearer-token / google-oauth-connector** — the credential this transport carries. The
  host-binding and no-cross-origin-redirect rules here are what stop that token leaking.
- **connector-egress-circuit-breaker** — wrap the calls this transport makes in that breaker so a
  hung/flapping provider fails closed instead of hanging.

## Reference implementation (TSS-own source)
`TSS/server/src/runtime/native-web-fetch.ts` — the whole pinned transport, all pure/testable:
- Address classification (every SSRF encoding collapses at the resolved IP):
  `classifyAddress` L238, `classifyIpv4` L139 (metadata/loopback/private/CGNAT/reserved), `classifyIpv6`
  L192 (IPv4-mapped `::ffff:` L197, 6to4 `2002::/16` L213, IPv4-compatible L217, Teredo/ISATAP refused L222).
- URL shape screen BEFORE any DNS (scheme allowlist L252, port allowlist L258, reject userinfo
  credentials L283): `screenUrl` L265.
- "ALL resolved addresses must be PUBLIC, else fail closed on the whole name; return the pinned address":
  `screenResolvedAddresses` L308.
- The socket **pin** — a custom `lookup` that always answers with the single validated IP so the socket
  can never re-resolve (anti-rebind): `defaultTransport` L404, `pinnedLookup` L414-424.
- Fresh per-request agent, `keepAlive:false` — no pooled socket reused for a host whose address changed:
  L430-432. TLS `servername` = real hostname + `rejectUnauthorized:true`: L450-451.
- TOTAL-deadline timeout (Node's `timeout` is only an inactivity timer; a byte-per-second dribble never
  trips it): `setTimeout(client.destroy(...))` L498-500. Byte cap + `res.destroy()` on overflow L457-467.
  Partial-body guard (`res.complete`) L477-480. `accept-encoding: identity` to sidestep decompression
  bombs L690-691, and refuse a server that compressed anyway L754-764.
- Per-hop redirect re-validation, https→http downgrade refusal L723-730, and **credentialed
  cross-origin redirect refusal** (a bearer/API-key/POST-body is scoped to its origin and is never
  replayed to a redirect target): `requestCarriesCredential` L565, refusal L737-744.
- Host-bound bearer read lane (a credential with no `allowedHosts` binding is refused; a credentialed
  read never follows a 3xx so the bearer cannot cross origins):
  `TSS/server/src/runtime/connector-transports.ts` — `governedHttpRead` L230, `isHttpReadCredentialHostBound` L223, redirect refusal L295-297.

Proof: `TSS/tests/native-web-fetch/run.ts` drives every SSRF encoding as an attack and asserts refusal.

## How to reapply (in a CLIENT build)
**Node / server backend (full technique):**
1. `screenUrl(raw)` first — allow only `http:`/`https:`, only public web ports, reject `user:pass@`.
2. Resolve with `dns.lookup(host, { all:true, verbatim:true })`, run `screenResolvedAddresses`; if any
   resolved IP is non-PUBLIC, refuse the whole hostname.
3. Open the socket with a custom `lookup` that returns ONLY the validated IP, on a fresh
   `new Agent({ keepAlive:false, maxSockets:1 })`, `rejectUnauthorized:true`, `servername:host`.
4. Do NOT auto-follow redirects (`node:http`/`https` don't) — loop yourself and re-run steps 1-3 on each
   `Location`; refuse https→http and any credentialed cross-origin hop.
5. Arm BOTH an inactivity `timeout` and a `setTimeout(() => client.destroy())` total deadline; cap bytes
   and `accept-encoding: identity`.
6. If sending a bearer, bind it to an `allowedHosts` list and refuse an unbound token; never follow a
   redirect on a credentialed request.

Return blocks/failures as VALUES (a typed `{ ok:false, code, reason }`), not thrown exceptions, so a
caller can tell "the page said X" from "I could not read the page."

**Cloudflare Worker (honest degradation — you CANNOT pin an IP):** Workers `fetch` gives no socket-level
`lookup`, so DNS-pinning is impossible. Get the achievable subset instead: (a) parse + allowlist the
scheme/port/host (prefer an explicit host allowlist over a blocklist), (b) `fetch(url,{ redirect:'manual' })`
and re-validate each `Location` yourself rather than auto-following, (c) `AbortSignal.timeout(ms)` for a
total deadline, (d) bound the body by reading a capped number of bytes from the stream, (e) never attach a
bearer unless the final host is on the allowlist. State in the build that Worker egress is host-allowlisted,
not IP-pinned, so the SSRF-via-rebind residual is accepted knowingly.

## Gotchas
- **Validate-then-connect without pinning is theatre.** Checking an address and letting the socket
  re-resolve is the exact DNS-rebind hole this closes; the pin is the whole security property.
- **IPv6 transition ranges embed IPv4.** `::ffff:127.0.0.1`, `2002:7f00:1::` (6to4) and IPv4-compatible
  forms route to the embedded IPv4 — classify them as that IPv4, not by their v6 prefix, or loopback
  slips through.
- **169.254.169.254 must be named specifically** — it sits inside link-local and is the highest-value
  target (cloud instance metadata / credentials).
- **A pooled/keep-alive agent breaks the pin** — a socket keyed by host:port can be reused for a host
  whose address has since changed. Fresh agent per request.
- **Node `timeout` alone never bounds a slow-drip server** — you need the total-deadline timer too.
- **A same-origin redirect keeps the credential; a cross-origin one must not.** Refuse (fail closed),
  don't silently forward — being publicly addressable does not make a host the credential's recipient.
- **Don't decode compression you didn't ask for** — request `identity` and refuse a body that came back
  compressed rather than guessing at a decompression bomb.
