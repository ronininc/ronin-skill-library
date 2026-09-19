# The free-tier playbook — building a CRM that stays on Cloudflare's free plan

The discipline that separates a CRM that runs free for years from one that surprises the client with a
bill. Every number below is from Cloudflare's live pricing docs (verified 2026-09; re-check at build
time — they move).

## The free ceilings you design against

| Service | Free allowance | What blows it |
|---|---|---|
| **Workers** | 100,000 requests/day | chatty UIs; N+1 `/api` calls. Batch + cache. |
| **D1 storage** | **500 MB per database**, **5 GB per account** | blobs in rows; no archival. Shard + R2. |
| **D1 rows read** | **5,000,000 / day** (enforced since 2026-09-01 — queries *fail* over it) | full table scans. **Index every filter/sort.** |
| **D1 rows written** | **100,000 / day** | bulk imports; remember an indexed write = 2 rows (table + index). |
| **R2** | 10 GB stored, 1M Class-A ops, 10M Class-B ops / month, **zero egress** | nothing realistic for a CRM. Put all blobs here. |
| **Workers AI** | **10,000 Neurons / day** (resets 00:00 UTC; over ⇒ errors) | re-embedding/re-summarizing on every view. Cache. |
| **Vectorize** | **Paid only — not on Free** | assuming semantic is free. Use the D1 fallback below. |
| **Pages** | free static hosting, unlimited sites | — |

## The ten master moves (how a senior builder stays free)

1. **Index every column you filter or sort on.** The 5M-reads/day cap is the one that bites first, and
   it's enforced now. A single unindexed `WHERE`/`ORDER BY` on a growing table scans the whole table
   per request → you hit the wall and queries start failing. Indexes are the cheapest free-tier
   insurance there is.
2. **Blobs never live in a D1 row.** Images, recordings, attachments, long HTML → R2 (10 GB free,
   zero egress), pointer in D1. This also protects the 2 MB row cap and the 500 MB DB budget.
3. **Shard across free 500 MB databases.** The same sticky, co-located-by-root overflow from
   `commerce-spine/sharding.md` works on free — you just cap at the **5 GB account total** (~10 DBs)
   before Paid is required. Most single-merchant CRMs never approach it; design for it anyway
   (global-unique text ids so a second shard never collides).
4. **Semantic without Vectorize (the free path).** Vectorize is Paid-only. On free: generate the
   embedding with Workers AI (within the neuron budget), **store the vector in a D1 column**, and rank
   with **cosine in the Worker** (`references/intelligence/semantic-d1-free.mjs`). Perfect for the
   hundreds-to-low-thousands of records a single CRM holds; migrate to Vectorize when you go Paid and
   N is large.
5. **Budget the 10k neurons/day.** Use the smallest model that works, **cache every summary/embedding
   in D1** (re-use, never re-run on each view), and make assist on-demand (a button), never automatic
   on list render. Scoring + forecasting are **pure JS = zero neurons** — lean on them first.
6. **Batch writes.** Bulk imports and activity logs can burn the 100k writes/day cap — write in
   batches, and remember every index multiplies the write count. Import jobs should chunk + checkpoint.
7. **Static UI on Pages, Worker for `/api/*` only.** `run_worker_first: ["/api/*"]` so the Worker only
   runs for data calls, not every asset — conserves the 100k requests/day.
8. **Degrade honestly at the wall.** The D1 daily caps return errors when exceeded. Catch them, show
   the operator "daily free limit reached — resets 00:00 UTC" (never a fake success), and let reads
   that don't need the DB keep working. Same for the neuron cap on assist.
9. **Cron sparingly.** Scheduled workers (feeds, reports, backups) each spend requests + reads/writes.
   Run them at a cadence the free caps absorb; a 15-min cron that scans is a reads-budget leak.
10. **Know the one-way door to Paid.** You move to Workers Paid ($5/mo) when you truly need: a single
    DB > 500 MB that can't shard, account storage > 5 GB, Vectorize at scale, > 10k neurons/day, or
    > 100k requests/day. Tell the client *which* limit forced it — never upsell before a real wall.

## Free-tier build defaults (what "ready for any customization" means on free)

- Substrate: D1 node, sharded-ready, R2 bound for blobs.
- Auth: cf-identity, PBKDF2 **100k** iters, login-lockout on.
- Intelligence: **scoring + forecasting on by default** (free, pure-JS); **assist on-demand + cached**;
  **semantic via the D1 fallback** (Vectorize only after Paid).
- Ops: append-only audit, data-quality flags, honest labels, scheduled D1 backup to R2.
- Everything indexed; blobs in R2; writes batched.

This is the baseline a senior builder ships on the free plan. Customize the record model on top of it
(`customization-guide.md`); the free-tier discipline doesn't change.
