---
name: team-messaging-board
description: >-
  An INTERNAL team/crew messaging board for a Cloudflare Worker + D1 staff portal — the Slack-lite comms
  half of a crew app, entirely sovereign (no Stream/Sendbird/Pusher). Conversation kinds: a one-way
  Announcements channel (managers post, everyone reads), a two-way company-wide channel every account
  auto-joins on creation, per-user private Support lines to the owners, 1:1 DMs (auto-reused), and
  ad-hoc groups; plus @-mentions, read receipts (last_read_at), and message bodies encrypted at rest. A
  simple polling read model (cursor + newest-first window) — no websockets. Use WHENEVER a staff/member
  portal needs "let the crew message each other", "team chat / internal messaging", "an announcements
  channel", "a whole-company channel", "DMs between staff", "a support line to the owner", "@ mention a
  teammate", or "who's read this". It COMPLEMENTS cf-identity (members ARE its users — do not rebuild
  auth), clearance-rbac (role rank gates who may post an announcement), and REQUIRES
  field-encryption-at-rest (message bodies). It is the INTERNAL counterpart to social-dm-inbox (that is
  EXTERNAL customer DMs off a platform webhook with window-gating; this is staff-to-staff). Do NOT use
  it for customer conversations. Guardrail: no foreign keys in D1, so validate every member/mention id
  against an ACTIVE user, and never let a mention become a way into a private thread.
---
# Team Messaging Board

## What it is / when to use / what it composes with
The internal comms subsystem of a crew portal: five conversation kinds, mentions, read receipts, and
encrypted bodies, on plain D1 with a polling read model. Members are **cf-identity** users; posting
rights lean on **clearance-rbac** role rank; bodies use **field-encryption-at-rest**. It is the
staff-side mirror of **social-dm-inbox** (which owns external, webhook-driven customer DMs).

## Reference implementation — exact source (all in `worker/index.js`, schema in `worker/migrations/`)
- **Schema:** `0001_init.sql` — `conversations(kind: group|dm|support|announcement)`,
  `conversation_members(…, last_read_at)`, `messages(body encrypted)`, `message_mentions`. `0008_whole_team.sql`
  adds `kind='team'`. Two fixed conversation ids seeded: `ANNOUNCE_ID` / `WHOLE_TEAM_ID` (`index.js:50-51`).
- **Reads:** `listConversations` (`:877`, pinned-first ordering via `pinRank`), `getMessages` (`:914`).
- **Writes:** `createConversation` (`:1026`), `postMessage` (`:1068`), `addMembers` (`:1122`),
  `markRead` (`:1152`), `getOrCreateSupport` (`:1161`).
- **Auto-membership:** `addToAnnouncements` (`:663`), `addToWholeTeam` (`:670`), `joinAllSupportLines` /
  `leaveOthersSupportLines` (`:677`/`:688`) — called from the account-approval flow.

## How to reapply
- **Kinds & membership model:** `announcement` (post gated to managers, everyone auto-joined),
  `team` (anyone posts, auto-joined, nobody can be manually added/removed), `support` (a private line a
  crew member has with the owners — created on demand, owners auto-added), `dm` (exactly two members,
  reused if one already exists — `:1042`), `group` (ad-hoc). Seed the announcement/team rows with FIXED
  ids so the Worker can address them like constants.
- **Posting rules (`postMessage`, `:1068`):** membership check first (403 if not in it); announcement
  posting requires `canManage` (`:1076`); encrypt the body (`encField`) before insert; bump
  `conversations.last_at`; return the PLAINTEXT the sender wrote, never the ciphertext.
- **Mentions only add on GROUP threads (`:1099`):** a mention pulls someone into a `group` thread, but on
  a `dm`/`support`/`announcement` a mention of a non-member is ignored (never a back-door in). Because
  history has no cutoff, letting a mention add someone to a private line would expose everything said
  before they arrived.
- **Polling read model (`getMessages`, `:914`):** client passes `after` = the last `created_at` it has;
  query `created_at >= ?` (NOT `>`) and de-dupe on message id client-side. First open returns the
  NEWEST 500 (`SELECT … ORDER BY created_at DESC LIMIT 500` wrapped and re-sorted ASC), not the oldest.
- **Read receipts:** `markRead` stamps `conversation_members.last_read_at`; the unread indicator is
  `last_msg_at > last_read_at`.
- **Wiring:** these are dispatched through a single `/api/rest`-style RPC switch behind the auth
  middleware; the account-approval path calls the auto-join helpers so a new hire lands in Announcements
  + the whole-team channel + their own support line.

## Gotchas
- **No foreign keys in D1** → every `member_ids`/`mention_ids` entry must be checked
  `SELECT 1 FROM users WHERE id=? AND active=1` before insert, or you write junk rows nothing cleans up
  (`createConversation:1036`, `addMembers:1135`, `postMessage:1106`).
- **`>=` cursor, not `>`** (`:919`): two posts in the same millisecond gave two rows with equal
  timestamps; `>` advanced the cursor past one and it was never delivered to anyone. Re-sending the
  boundary is free because the client de-dupes on id.
- **Empty `addMembers` must not flip a DM to a group** (`:1145`): only promote `dm→group` when
  `added>0`, else an empty call silently converts a private DM to a "group," re-opening the mention path.
- `support`/`announcement`/`team` reject manual `addMembers` (`:1126`) — their membership is auto-managed.
