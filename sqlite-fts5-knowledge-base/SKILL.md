---
name: sqlite-fts5-knowledge-base
description: >-
  A SOVEREIGN, fully-offline full-text search brain for any CRM/app/site: turn a pile of documents
  (help articles, product docs, policies, past tickets, a client's own reference library) into
  per-topic SQLite FTS5 shards with BM25 ranking, then answer a query in milliseconds by ROUTING it
  to the relevant shard(s) via a keyword map, running an FTS `MATCH`, and rank-fusing the hits — no
  embeddings, no model, no network, no third-party service. Includes the whole plumbing: a crash-safe
  idempotent index BUILDER (temp shard + atomic rename, batched transactions, verify-once by mtime),
  a heterogeneous EXTRACTOR (chunk + provenance-tag CSV/MD/HTML/XML/JSONL/wiki dumps into index-ready
  JSONL with staging→commit→receipt resumability), a READER (cached read-only handles that self-detect
  a live re-index swap, quoted-term OR match, cross-shard rank fusion because BM25 is not comparable
  between shards), and a PRESENCE GATE (ABSENT/PARTIAL/PRESENT that actually opens each shard to confirm
  it holds rows, plus a disk preflight). Use WHENEVER a build needs "search our docs/knowledge base",
  "let users ask questions of a document set", "keyword/full-text search over records or files",
  "a help center search", "find the relevant policy/article", "index these documents so we can search
  them", "on-device / offline search", or "search without paying for a vector DB or LLM". It COMPLEMENTS
  vectorize-semantic-layer (that is MEANING search via Cloudflare Workers-AI embeddings + a Vectorize
  binding, needs egress/provisioning — this is LEXICAL BM25, sovereign and offline; ship both and merge
  for hybrid search), agnostic-import-parser and data-feed-intake (those bring foreign records/files
  IN — this makes free text SEARCHABLE afterwards), and admin-search-export (that is exact-identifier
  lookup — this is ranked full-text). Guardrail: FTS5 is lexical, not semantic; a query is quoted and
  OR-joined so a stray FTS operator can't reinterpret it; the presence gate never trusts a file's mere
  existence.
---
# sqlite-fts5-knowledge-base — sovereign per-shard FTS5 search + BM25

## What it is / when to use
The lexical retrieval half of an app's intelligence, kept sovereign by living entirely inside SQLite
(node:sqlite / better-sqlite3 locally, or a D1 binding on Cloudflare). Reach for it when you have a
BODY OF TEXT — docs, articles, policies, past cases, a client's uploaded reference set — and users
need to *find the relevant passages* by what they typed, in milliseconds, with no per-query cost and
no data leaving the machine. It is a document/passage search engine, distinct from:
- **exact-identifier lookup** (`admin-search-export`) — that finds a record by name/email/id; this ranks free text;
- **meaning search** (`vectorize-semantic-layer`) — that embeds text and needs a Cloudflare AI + Vectorize binding + egress; this is BM25 keyword ranking, fully offline. They compose: run both and merge for hybrid recall;
- **ingest** (`agnostic-import-parser`, `data-feed-intake`) — those get foreign data *in*; this indexes text so it can be *searched*.

It composes with `d1-migration-recipes` (ship the FTS schema as an additive migration), `commerce-spine` / `crm-build-standard` (the per-site DB it indexes), and `chunked-uploader` (the files it extracts).

The design principle: **one database per topic ("field").** A query has no business scanning the whole
library, so a keyword router decides WHICH shard(s) to open, and only those are `MATCH`ed. This is what
lets a multi-GB corpus answer on an 8 GB machine — the inverted index does the work, nothing is loaded
into memory to be scanned.

## Reference implementation (exact files — lift from here)
Four cooperating pieces plus a routing contract. All paths are TSS-own source.

**1. The routing contract** — `contracts/knowledge-fields.json`
- A JSON array of `{ field, triggers, description, authorityBias, optional? }`. `triggers` is a
  case-insensitive regex; if it matches the query, that field's shard is nominated. This is the
  entire "which database does this question belong to" map — declarative, hot-editable, no code.

**2. The index BUILDER** — `scripts/solomon-index-knowledge.mjs` (turns one JSONL of chunks → one `<field>.db`)
- **Schema** L40-44: `CREATE VIRTUAL TABLE chunks USING fts5(text, title, sourceId UNINDEXED, chunkNo UNINDEXED, refs UNINDEXED, tokenize='unicode61 remove_diacritics 2')`. Only `text`+`title` are searchable; provenance columns ride along UNINDEXED so a hit is renderable. `remove_diacritics 2` folds accents so "Nahuatl"/"Náhuatl" match.
- **Verify-once / idempotent** `needsReindex` L62-70 + `shardUsable` L49-60: re-index a field ONLY when its source JSONL is newer than the `.db` **AND** the existing `.db` actually opens and holds ≥1 row. A fresh mtime alone is not proof — an empty/corrupt/chunkless shard opens to zero hits, so it must be rebuilt.
- **Crash-safe build** `indexField` L72-137: write into `<field>.db.building`, `PRAGMA journal_mode=WAL; synchronous=NORMAL` (L88), insert in **batched transactions** (`BEGIN`…5000 rows…`COMMIT`, L92-120 — per-row autocommit fsync makes a million-row field take hours), `INSERT INTO chunks(chunks) VALUES('optimize')` (L122) to merge FTS segments, `wal_checkpoint(TRUNCATE)` (L124), then **atomic `renameSync(tmp, db)`** (L133). A kill mid-build leaves only the `.building` file; the live shard is never removed before the rename, so the field is always either the previous complete shard or absent-and-rebuildable, never a truncated shard that looks done.
- **Fail-the-build on bad data** L102-114: a malformed non-empty JSON line ABORTS the build without the atomic swap, so a dropped record can never be silently frozen into a "complete" shard.

**3. The heterogeneous EXTRACTOR** — `scripts/solomon-extract-knowledge.mjs` (raw files → chunked provenance JSONL)
- Format dispatch `extractField` L347-424: plain text/MD/RST/HTML/XML, JSONL (+`.gz`), and STREAMING MediaWiki `.xml.bz2/.gz` dumps (decompressed via a piped child, L228-256, so a multi-GB dump never loads into RAM). Normalizers L38-55.
- **Chunking + provenance** `makeSink` L132-161: accumulate to ~3500 chars, then emit one JSONL line `{ field, sourceId, chunk, title, language, refs, chars, text }`. `refs` (L139) captures outbound URLs in the chunk — a hook for later reference-checking.
- **Resumable staging→commit→receipt** L93-130, L388-420: a source's chunks stream to a private `.staging/<id>.part`; only `commitStagedSource` folds it into the shared JSONL (in bounded 1 MiB blocks, with a pre-append offset marker so a crash mid-merge is truncated back and retried); then a per-source receipt (`path:size:mtime`) is written. A source is re-extracted only when its receipt key no longer matches — a changed source is REPLACED (drop-old-chunks only *after* the new extraction succeeds), a vanished source is reconciled out.

**4. The READER** — `server/src/runtime/knowledge-index.ts` (query → ranked hits)
- `routeFields(query)` L70-78 + `loadRoutes` L57-67: run each field's `triggers` regex; the matches are the nominated shards. **Empty ⇒ fall back to every available shard** (correct, just less selective). A nominated-but-absent shard does NOT license sweeping unrelated fields (L197-203) — that would let off-topic generic-term hits masquerade as evidence.
- `openField` L101-113 + `shardSignature` L96-99: cache read-only handles (`new DatabaseSync(path, { readOnly: true })`), keyed on **file identity** `ino:mtimeMs:size`. A live re-index atomically swaps the `.db` underneath a long-lived process; a cheap `stat` per lookup detects the swap and reopens, so answers stay current without giving up the cached-handle win.
- `queryKnowledge` L185-228: `substantiveTerms(query)` → **quote every term and OR-join** (`"foo" OR "bar"`, L192) so a stray FTS5 operator in the question can't reinterpret the `MATCH`, and recall stays high while BM25 floats the chunks carrying the most terms. Query is `SELECT …, bm25(chunks) AS score FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?` (L213-215), collected **per shard**.
- `fuseCrossShardHits` L153-168 (the subtle one): **BM25 scores are NOT comparable between independently-built shards** (each depends on its own corpus statistics). A global sort by raw score lets one shard's scale dominate and evict better hits from another field. Instead, interleave by **per-shard rank** (best hit of every routed field competes before any field's second hit), tie-break on a corpus-INDEPENDENT term-coverage relevance (`sharedRelevance` L130-142), then a stable field/source/chunk order for determinism.
- `referenceLibraryContext` L249-255: a bounded, ready-to-inject `{title, summary, sourceKind}[]` (6 hits, text sliced) for feeding a model context window without blowing it up.

**5. The PRESENCE GATE** — `desktop/knowledge-provision.mjs`
- `knowledgeRoots(env)` L53-62: one env-resolved set of roots (`sources`/`extracted`/`index`) so builder and reader never diverge.
- `shardHasChunks(db)` L124-135 + `knowledgeStatus(env)` L151-201: compute **ABSENT / PARTIAL / PRESENT live from disk**, never a build-time manifest. A shard counts as present only if it opens read-only AND `SELECT 1 FROM chunks LIMIT 1` returns a row; anything else is flagged STALE → the library reads PARTIAL, never PRESENT. This is the honest-degrade gate: a half-built or corrupt library is reported as partial, and the app falls back (e.g. to live web) rather than answering from nothing.
- `diskPreflight` L219-234: refuse a provisioning run up front if the volume can't hold the working set — a disk that fills mid-write corrupts a shard.

## How to reapply (in a CLIENT build)
1. **Decide the shards.** Ship a `fields.json` routing contract: one entry per topic the client's docs
   cluster into (e.g. `products`, `policies`, `faq`, `past-tickets`), each with a `triggers` regex.
   One shard for a small set is fine — routing just no-ops and you `MATCH` the single DB.
2. **Extract once.** Walk the client's uploaded/imported files; chunk each to ~1–4k chars; write
   `{ sourceId, title, text, chunkNo, refs }` JSONL per field. Keep the staging→commit→receipt
   discipline if the corpus is large or the run can be interrupted; skip it for a one-shot small set.
3. **Build the shard(s)** with the FTS5 schema above — batched transactions, `optimize`, build-to-temp
   + atomic rename. Re-run is cheap because of verify-once.
4. **Query** with the reader: `substantiveTerms` → quoted OR `MATCH`, `ORDER BY bm25(chunks)`, per-shard
   collect, `fuseCrossShardHits`. Return `{title, text, sourceId, score}` and cite the source.
5. **On Cloudflare D1:** the SAME FTS5 schema works — ship it as an additive migration
   (`d1-migration-recipes`), populate rows via `INSERT`, and query through the Worker's D1 binding
   (`env.DB.prepare('… WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?').bind(match, k).all()`).
   The build-to-temp+rename and the file-identity handle cache are LOCAL concerns (they solve
   crash-safety of a file on disk); D1 handles durability, so on D1 you keep the schema, the quoted-OR
   match, the BM25 order, and the cross-shard fusion, and drop the atomic-rename builder.

## Gotchas
- **BM25 is not cross-shard comparable.** If you query more than one shard, you MUST rank-fuse by
  per-shard rank, not by raw score. Skipping this silently biases results toward whichever shard has
  the more extreme score scale. (`fuseCrossShardHits`.)
- **Existence ≠ usable.** A `.db` with a fresh mtime can be empty, truncated, or missing its `chunks`
  table (opens to zero hits). Both the builder's `needsReindex` and the gate's `shardHasChunks` OPEN
  the shard and confirm a row. Never gate on file presence alone.
- **Quote and OR-join every term.** Raw user text through `MATCH` lets a stray `"`, `*`, `OR`, `NEAR`
  reinterpret the query or throw. Quote each term; OR for recall; let BM25 do the ranking.
- **`remove_diacritics 2`** in the tokenizer is what makes accented/multilingual text match its
  unaccented form. Set it at `CREATE VIRTUAL TABLE` time — you cannot change tokenizer after.
- **Live re-index swaps the file.** If a long-lived reader caches a bare connection, it serves the OLD
  shard until restart. Cache keyed on `ino:mtime:size` and reopen on change (`shardSignature`).
- **Empty route ⇒ all shards; absent nominated shard ⇒ NOT all shards.** Getting this backwards either
  kills recall or lets off-topic hits pose as on-topic evidence.
- **FTS5 is lexical.** "car" won't match "automobile". For synonym/meaning recall, run
  `vectorize-semantic-layer` alongside and merge — this skill is the sovereign/offline half.
