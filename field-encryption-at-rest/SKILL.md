---
name: field-encryption-at-rest
description: >-
  The reusable helper for encrypting individual sensitive TEXT columns at rest in a Cloudflare Worker +
  D1 app with ONE secret and Web Crypto — a reversible AES-GCM `encField(env,text)` / `decField(env,stored)`
  pair (distinct from a one-way password hash). Bodies/notes/PII are written as `base64(iv):base64(ct)`,
  read back transparently, degrade to plaintext when no key is set (dev), tolerate legacy/seed plaintext,
  and on a KEY MISMATCH return a loud "[unreadable — the key changed. Do not delete this message.]"
  instead of on-screen gibberish that gets deleted. Use WHENEVER a build stores free text you would not
  want readable in a DB dump — "encrypt messages/notes at rest", "encrypt customer PII / phone / email",
  "field-level encryption", "AES-GCM in a Worker", "don't store chat bodies in plaintext", "encryption
  key for the app". This is the SHARED helper that several skills say they use but none defines: it
  COMPLEMENTS cf-identity (which owns the ONE-WAY PBKDF2 password hash — this is the REVERSIBLE
  field-crypto beside it) and is the "encrypted at rest" primitive behind social-dm-inbox (DM bodies),
  services-delivery-lifecycle (scope/notes), and wire-payment-collect-reconcile (wire instructions).
  Guardrails: AES-GCM with a fresh 12-byte IV per value; the key is a Worker secret, never in D1, never
  logged; losing the key means the ciphertext is unrecoverable — say so and never silently destroy it.
---
# Field Encryption at Rest

## What it is / when to use / what it composes with
Two ~15-line async functions that make specific columns ciphertext at rest with a single
`ENCRYPTION_KEY` secret, and are safe to sprinkle at every read/write site because they no-op cleanly
when the key is absent and tolerate plaintext. It is the reversible counterpart to **cf-identity**'s
one-way password hashing, and the concrete "encrypted at rest" helper that **social-dm-inbox**,
**services-delivery-lifecycle**, and **wire-payment-collect-reconcile** all reference but leave
undefined. It pairs naturally with **team-messaging-board** and **service-invoice-ledger** (their
bodies/PII columns).

## Reference implementation — exact source
`worker/index.js:334-393` — `keyMaterial()`, `getKey()` (cached), `encField()`, `decField()`.
Storage format: `base64(iv) + ':' + base64(ciphertext)`, AES-GCM, IV is 12 random bytes per value.

## How to reapply
**1. Key ingestion (`keyMaterial`/`getKey`, `:334`):** accept the secret as EITHER base64 of 16/24/32
raw bytes (used directly) OR any passphrase (hashed with SHA-256 to a 32-byte key). Import once with
`crypto.subtle.importKey('raw', raw, {name:'AES-GCM'}, false, ['encrypt','decrypt'])` and **cache** the
`CryptoKey` keyed by the secret string (module-level `_cryptoKey`/`_cryptoKeyB64`) so it is derived once
per isolate, not per field.
**2. Encrypt (`encField`, `:355`):** `null`→`null`; no key→return the text unchanged (dev fallback);
else fresh `getRandomValues(12)` IV, `encrypt`, return `b64(iv)+':'+b64(ct)`.
**3. Decrypt (`decField`, `:363`):** `null`→`null`; no key→return stored; no `:`→plaintext (seed data);
split on the FIRST `:`, and if either half is not valid base64 or the IV isn't 12 bytes, treat as
plaintext (a seed string that merely contains `:` must still read as itself); only when it is genuinely
ciphertext-shaped do you `decrypt`.
**4. Apply it at every I/O site** — encrypt on the way in, decrypt on the way out, and always return the
plaintext the caller just submitted (never re-read the ciphertext). Working sites in this repo:
messages (`:1082` write / `:945` read), job notes (`:1534` / `:1001`), invoice customer PII
name/email/phone/financing (`:1623-1626` / `:1798-1801`), leads (`:2380`). Because `batch()` takes
prepared statements, not promises, **await all `encField` calls BEFORE building the batch array**.
**5. Provision the secret** (do NOT put it in `wrangler.jsonc`):
```
KEY=$(openssl rand -base64 32); echo "$KEY" | npx wrangler secret put ENCRYPTION_KEY
```
The schema documents the encrypted columns as holding `base64(iv):base64(ciphertext)` (see
`worker/migrations/0001_init.sql` header).

## Gotchas
- **Key-mismatch is the dangerous case.** If a value IS ciphertext-shaped but decryption throws, the key
  changed. Returning `stored` puts base64 gibberish on screen dressed as a real message — in a thread
  where the obvious reaction is to delete "the noise," i.e. destroying recoverable data. Instead
  `console.error` it and return `'[unreadable — the encryption key changed. Do not delete this message.]'`
  (`:390`). Loud, safe, diagnosable.
- **Lose the key, lose the data** — there is no recovery. Save `ENCRYPTION_KEY` somewhere durable before
  real data lands.
- It encrypts at REST only; the value is plaintext in the isolate and over TLS — this is protection
  against a DB dump / backup leak, not a substitute for auth or transport security.
- GCM's auth tag is inside the ciphertext, so a tamper/truncation surfaces as a decrypt throw (handled
  above), not silent corruption. Do not swap to CBC.
