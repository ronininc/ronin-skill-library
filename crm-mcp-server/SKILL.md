---
name: crm-mcp-server
description: >-
  Turn any Cloudflare Worker + D1 client CRM into a remote MCP SERVER an external brain can drive — a
  bearer-gated, role-scoped set of Zod-typed tools mounted at their own routes (e.g. /mcp, /mcp/solomon,
  /mcp/kingmaker) so an AI operator can READ and ACT on the CRM under governance. Use WHENEVER a build
  needs to be "operable/observable by an AI", "give Solomon/Codex/an agent MCP access to the CRM", "let
  my assistant run the pipeline", "expose CRM tools over MCP", "a remote MCP endpoint", or "an operator
  brain that works while I'm out." This is the SERVER layer only — it COMPLEMENTS scoped-bearer-token
  (which mints/hashes/revokes the tokens — reuse it, don't reissue tokens here) and clearance-rbac (the
  scope→permission model whose scopes each tool checks before writing). For the WEB chat operator surface
  use governed-operator-console; for the sanitized one-way oversight feed use governance-diode — this skill
  is the transport that both of those ride on. Guardrails: host + Origin allowlist on every request,
  per-token scope guard on every write tool, honest readOnly/idempotent annotations, and money/irreversible
  actions never auto — expose them as propose-only or leave them off the server.
---
# crm-mcp-server — your CRM as a governed remote MCP surface

The Model Context Protocol lets an external brain (Codex Desktop, an agent, Solomon) call typed tools over
HTTP. This skill is the pattern for hosting that server INSIDE the CRM's own Worker: same D1, same auth
table, no separate service. Each tool is Zod-typed, annotated with real read/write hints, and — for writes
— gated on the calling token's scopes. Different roles get different tool sets at different routes.

## What it is / when to use
The remote-MCP-server-in-a-Worker add-on. Reach for it on any CRM that should be drivable by an AI
operator, not just a human in the admin UI. It is a universal bolt-on: define the tools once, gate them by
scope, mount a handler per role.

**Composes with:** **scoped-bearer-token** (the `mcp_api_tokens` table, SHA-256 hash-store, mint + revoke,
role→scope bundles — this skill AUTHENTICATES against it but does not own it), **clearance-rbac** (the
scope vocabulary a tool checks, e.g. `crm:write`, `social:read`). It is the transport under
**governed-operator-console** (a broad operator role) and **governance-diode** (a sanitized oversight
role). Individual tools wrap existing CRM functions — the MCP layer adds typing, scoping, and annotations,
not business logic.

## Reference implementation (ronininc — read these)
- **A capability-scoped connector server** — `worker/opportunity-mcp.ts` (whole file, 1-138). Shows
  `McpServer` + `registerTool` with Zod input schemas + `annotations`, and per-tool scope checks
  (`allowed.has('social:read')` at `:100-102`, `social:write` at `:110`). The route handler
  `handleOpportunityMcp` (`:118-137`) does the host/Origin allowlist and calls `createMcpHandler`.
- **A broad operator server** — `worker/solomon-mcp.ts` (whole file, 1-353). Same shape at scale: ~20
  tools, a single `guardWrite()` (`:53`) applied to every mutating tool, and a role gate in the handler
  (`:346` requires `crm:read`).
- **Auth + roles** — `worker/opportunity-markets.ts:297-369`: `hashToken` (`:297-299`), `MCP_ROLE_SCOPES`
  + `roleFromScopes` (`:305-315`), `issueMcpToken` (`:317-333`), `listMcpTokens` (`:336-346`),
  `revokeMcpToken` (`:348-355`), and `authenticateMcp` (`:357-369`) — the one function every MCP handler
  calls first.
- **Routing** — `worker/index.ts:151-162` (mount `/mcp`, `/mcp/solomon`, `/mcp/kingmaker` before ASSETS,
  wrap in `withSecurity`, per-path handler dispatch).
- **Token admin UI** — `public/admin/admin.js:683-730` (issue Solomon/Kingmaker token, show the secret
  ONCE, list + revoke).
- Deps: `@modelcontextprotocol/server` (`McpServer`), `agents/mcp/server` (`createMcpHandler`, the
  Cloudflare Agents SDK), `zod`.

## How to reapply it
1. **Reuse the token machinery from scoped-bearer-token** — you need `mcp_api_tokens` (id, name,
   token_prefix, token_hash, scopes, created_by, expires_at, revoked_at, last_used_at), `hashToken`
   (SHA-256 hex), a `MCP_ROLE_SCOPES` map (role → space-separated scope string), `issueMcpToken` (mint a
   `prefix_<randomHex>`, store only the hash, return the plaintext ONCE), `revokeMcpToken`, and
   `authenticateMcp(req, env)` → `{id, scopes}` or a 401 `Response`.
2. **Build a server factory** per role: `createXServer(env, scopes)` returns an `McpServer`; inside,
   `const allowed = new Set(scopes.split(/\s+/))` and `registerTool(name, {title, description, inputSchema:
   z.object({...}), annotations}, handler)`. Set `annotations` honestly: `readOnlyHint: true` for reads,
   `idempotentHint: true` for set-status style writes, `openWorldHint: true` when it calls an external API.
3. **Gate every write** at the TOP of its handler: `const g = guardWrite(); if (g) return g;` where
   `guardWrite = () => allowed.has('crm:write') ? null : denied('read-only')`. Return the MCP error shape
   `{ isError: true, content: [{ type:'text', text: '…' }] }`, never throw raw.
4. **Route handler** — `handleXMcp(req, env, ctx)`: (a) check `url.hostname` against an ALLOWED_HOSTS set
   (plus `*.workers.dev` for staging); (b) if an `Origin` header is present, parse it and reject a
   non-allowlisted host; (c) `authenticateMcp`; (d) enforce the role's required scope
   (`if (!scopes.includes('crm:read')) return 403`); (e) `createMcpHandler(() => createXServer(env,
   auth.scopes), { route, corsOptions:false, allowedOriginHostnames, authContext:{ props:{ tokenId,
   scopes } } })` and return `handler(req, env, ctx)`.
5. **Mount** in the Worker's top-level `fetch` (not under `/api/admin/*`) and wrap the response in your
   security-header helper. One route per role.
6. **UI** — an admin card that POSTs to issue a token by role, reveals the secret exactly once in a
   read-only field, and lists tokens by prefix + role + active state with a revoke button.

## Gotchas (from the code)
- **Scope is the whole security model.** A tool with no `guardWrite()` is callable by any valid token.
  Audit each `registerTool` for its guard; a read-only role must not reach a write tool.
- **Host AND Origin, both.** The host allowlist stops the wrong deployment; the Origin check stops a
  browser on another site from driving your MCP with a stolen token. Reject a malformed Origin outright.
- **Store only the token HASH.** `issueMcpToken` returns the plaintext once and never again — the DB has
  `token_hash` only. The UI must say "copy it now, shown once." `authenticateMcp` hashes the presented
  token and looks up the hash.
- **`last_used_at` on every auth** gives you a cheap liveness/abuse signal; write it in `authenticateMcp`.
- **Annotations are advisory to the client but a discipline for you** — labelling a mutating tool
  `readOnlyHint: true` will mislead the operator brain into calling it freely. Keep them truthful.
- **Money / irreversible actions.** Follow the reference: the server exposes DRAFT/propose tools (e.g.
  "draft a bid" that never submits externally) and status moves, not "send money." Keep irreversible steps
  off the auto server or behind a human-confirm surface (governed-operator-console).
- **`expires_at` + `revoked_at` are checked in the auth SQL**, not in app code — an expired token simply
  doesn't match the `WHERE`. Mint with a bounded default (e.g. 90 days) and re-mint rather than issuing
  non-expiring tokens.
