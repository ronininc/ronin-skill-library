---
name: local-message-store-crm-relay
description: >-
  Put the texts from the operator's OWN phone onto the CRM contact timeline WITHOUT the messages
  ever leaving the machine unless they belong to a known contact — by reading the Mac's Messages
  store (chat.db) READ-ONLY and gating every conversation through a SALTED-HASH contact filter: the
  relay fetches salted hashes of the CRM's contact numbers, hashes each local conversation's number
  the same way, and only a hash MATCH lets that text push; every other message is skipped on the box
  and never transmitted. It is watermark-idempotent (each text stored once, re-runs harmless),
  decodes the modern typedstream attributedBody (where macOS leaves the plain text NULL), handles
  one-on-one chats only (no groups, no tapbacks), and turns an inbound "STOP" into a do-not-call
  the same as a carrier opt-out. Use WHENEVER a build needs "my texts on the customer's timeline",
  "log iMessage/SMS to the CRM", "see the conversation history with this lead", "pull my phone
  messages into the CRM privately", or "a local relay that files my texts without uploading my whole
  message history". COMPLEMENTS text-campaign-platform (its OUTBOUND cousin — that drains a send
  queue to your number; this INGESTS the replies/history), social-dm-inbox (webhook DMs vs local
  device texts), quick-capture-inbox (where a matched note lands), and residential-edge-relay (the
  bearer-push contract it rides). Guardrails: READ-ONLY on chat.db (never send/alter a message);
  ONLY messages matching a hashed CRM contact ever leave the Mac; one-on-one only; STOP → shared DNC;
  the token can live in the login Keychain, never a plist; needs Full Disk Access, granted by the
  operator.
---
# Local Message Store → CRM Relay

## What it is / when to use / what it composes with
A CRM on the edge can't see the operator's texts; their Mac can (Messages syncs every iMessage, and
with Text Message Forwarding on, every SMS, into `~/Library/Messages/chat.db`). This relay reads that
store read-only and files texts onto the matching contact's timeline — but its defining move is
**privacy by salted-hash scoping**: the operator's entire message history stays on the box, and only
a message whose phone number hashes to a number the CRM already knows is ever transmitted. It is the
inbound half of a two-way phone bridge.

- **Not `text-campaign-platform`:** that is OUTBOUND — a local sender drains a send queue from your
  number. This is INBOUND — it ingests the resulting conversation into the timeline.
- **Not `social-dm-inbox`:** that receives platform DMs via an HMAC webhook. This reads a local
  device's own SQLite message store.
- **Composes with:** `residential-edge-relay` (bearer push/pull to the Worker),
  `outbound-compliance-gate` / the shared DNC (STOP handling), `quick-capture-inbox` (a matched text
  can graduate to a capture/task), and `crm-build-standard` (the contact/timeline spine).

## Reference implementation — exact source (lift the proven code)
`~/ronin-osint/imessage-relay.py`:
- **The privacy contract, in words:** docstring `imessage-relay.py:11-16` — only texts whose number
  matches a CRM contact ever leave the Mac; one-on-one only; never sends or changes a message.
- **Salted-hash scoping (THE INVARIANT):** the relay GETs `{salt, keys[]}` (`:227-229`), then for
  each row computes `sha256(salt + e164_number)` and pushes only on a set membership hit —
  `imessage-relay.py:181`. Numbers themselves are never uploaded to decide membership; the hash is.
- **E.164 normalization (must match the CRM's):** `e164(raw)` — `imessage-relay.py:75-87` (drops
  iMessage-by-email; US-default +1).
- **Apple-time → unix:** `unix_time()` handles ns (modern) and s (old) — `imessage-relay.py:90-93`.
- **typedstream body decode (the macOS-13+ gotcha):** `decode_attributed_body(blob)` pulls text from
  the `attributedBody` when `message.text` is NULL, with a printable-run fallback that filters class
  names — `imessage-relay.py:96-116`.
- **One-on-one, real messages only:** `QUERY` — `c.style = 45 AND m.item_type = 0 AND
  COALESCE(m.associated_message_type,0)=0` (no groups, no tapbacks) — `imessage-relay.py:156-165`.
- **Read-only DB open:** `open_db()` uses `mode=ro` URI — `imessage-relay.py:143-144`.
- **Watermark idempotency:** push new rows since the stored ROWID, advance the watermark ONLY after a
  successful push, batch to the server cap — `imessage-relay.py:168-200`,`232-235`; first-run
  baseline / optional `--backfill-days` — `imessage-relay.py:147-152`,`215-219`.
- **Secret from the login Keychain (not a plist):** `imessage-relay.py:53-61`.

## How to reapply — the wiring + THE INVARIANT
1. **Keys endpoint:** the Worker exposes `GET /api/relay/texts/keys` → `{salt, keys:[sha256(salt+
   number)]}`, refreshed on a TTL (`imessage-relay.py:65`,`227-229`). The salt rotates the hashes so
   the key list isn't a reversible phone book.
2. **Local match, then push:** read new rows past the watermark, `e164`-normalize each number, hash
   with the salt, and push ONLY set members to `POST /api/relay/texts` in batches
   (`imessage-relay.py:179-197`).
3. **Advance the watermark only on success** so a failed push re-tries the same rows next cycle
   (`imessage-relay.py:232-235`) — this is what makes "store each text once" true.
4. **STOP → DNC:** an inbound opt-out flips the shared do-not-call, same as a carrier text (docstring
   `:21-22`; the server counts `opt_outs` in its reply `:197`).

**THE INVARIANT:** the operator's full message history never leaves the machine — only a message
whose number hashes to a known CRM contact is transmitted, and even the matching is done against
salted hashes, not raw numbers. The relay is strictly read-only on the message store: it files
history, it never sends or edits a text.

## Gotchas — real pitfalls from the code + how it's validated
- **`message.text` is NULL on modern macOS.** You MUST decode `attributedBody`
  (`imessage-relay.py:96-116`) or you'll push empty bodies. The length-prefix parse (0x81/0x82 wide
  forms) is the fiddly part; the printable-run fallback saves the rest.
- **Full Disk Access is mandatory.** chat.db is TCC-protected; without granting the running terminal
  FDA the open fails with "unable to open database file" — the relay catches this and says exactly
  what to fix (`imessage-relay.py:220-222`).
- **Groups and tapbacks pollute a timeline.** The `style=45` + `item_type=0` +
  `associated_message_type=0` filter is deliberate; loosen it and you'll ingest reactions and group
  spam (`imessage-relay.py:156-165`).
- **E.164 must match the CRM's normalizer exactly**, or a real contact's hash never matches and
  nothing pushes (`imessage-relay.py:75-87`). Test with `--once --dry-run`, which shows matched vs
  skipped counts without sending (`imessage-relay.py:189-193`).
- **Backfill once, carefully.** `--backfill-days` on the FIRST run sets the baseline into the past;
  after that the watermark drives everything. Deleting the state file re-backfills
  (`imessage-relay.py:215`).
- **Ships dark by operator policy.** Per the operator's own notes the phone-text relay is currently
  DISABLED as a business decision (not a bug) — capture the technique; don't assume it's running. An
  arm-gate on the accept side makes that safe.
