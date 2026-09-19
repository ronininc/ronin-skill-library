---
name: d1-work-queue
description: >-
  Atomic per-item claim on a shared D1 queue with no double-processing: a single conditional
  UPDATE (set status='serving', claimed_by=me WHERE status='queued') makes it first-writer-wins,
  so N concurrent workers pulling from the same queue never grab the same row — plus time-based
  stale reclaim that returns a row an operator started but abandoned (closed the tab, crashed)
  back to the pool. Pure Cloudflare Worker + D1 (SQLite); no Durable Object, KV, Redis, or queue
  service. Use WHENEVER multiple workers/agents/tabs draw from one shared list and each item must
  go to exactly one of them — "claim a lead / job / ticket", "don't let two agents call the same
  contact", "no double-dial", "hand each row to one worker", "shared work queue", "lease a task",
  "atomic dequeue on D1/SQLite", "serve next without collisions", or "reclaim stuck/abandoned
  jobs". Backend concurrency primitive. Guardrails: SQLite has no SELECT…FOR UPDATE, so the
  conditional UPDATE + rows-changed check IS the lock — never SELECT-then-UPDATE (it races); trust
  result.meta.changes, not a prior read; loop over the top-N candidates so concurrent workers fall
  through to different rows; stale reclaim is purely time-based (tune the cutoff carefully). This
  is the concurrency guts under crm-build-standard's power-dialer daily queue — that skill wraps
  it with the queue-build, compliance, and disposition→learning loop; use THIS when you just need
  the claim-once primitive on any shared D1 job table.
---

# d1-work-queue — claim-once dequeue on D1 (no double-processing)

## What it is / when to use
The concurrency primitive for a shared queue on D1/SQLite: an atomic conditional UPDATE that
gives each queued row to exactly one worker (first writer wins) and a time-based reclaim that
frees rows a worker started but never finished. Reach for it whenever many agents/tabs/cron
invocations draw from one list and an item must be processed once — leads, jobs, tickets, render
tasks. When you need the whole governed power-dialer (build the daily list + compliance +
disposition→learning), use `crm-build-standard`; this is the claim-once mechanism underneath.

## Reference implementation (extracted from — open before lifting)
Wavelygth build (`~/Projects/clients/wavelygth`), a Cloudflare Worker + D1 shared "call_queue"
worked by multiple agent seats at once:
- **Backend** `worker/index.js` L2451-2493 (`handleDialerNext`) — the two moves:
  - **Stale reclaim** (before serving): `UPDATE call_queue SET status='queued', claimed_by=NULL
    WHERE day=? AND status='serving' AND (locked_at IS NULL OR locked_at < ?)` with a
    `now − 10min` cutoff — returns abandoned rows to the pool.
  - **Atomic claim** (inside a loop over the top-25 eligible candidates): `UPDATE call_queue SET
    status='serving', claimed_by=?, locked_at=? WHERE day=? AND lead_id=? AND status='queued'`,
    then `if (!claim?.meta || claim.meta.changes < 1) continue;` — whoever's UPDATE lands first
    wins; everyone else falls through to the next candidate. `.catch(() => ({meta:{changes:0}}))`
    so a transient error falls through instead of throwing mid-loop.
- **Schema**
  - `worker/migrations/0009_dialer.sql` — `call_queue (day, lead_id, position, priority, status
    DEFAULT 'queued', outcome, locked_at, PRIMARY KEY (day, lead_id))` + index
    `ix_queue_day (day, status, position)`.
  - `worker/migrations/0014_dialer_seats.sql` — `ALTER TABLE call_queue ADD COLUMN claimed_by
    TEXT` (NULL = free) + index `ix_queue_claim (day, status, claimed_by)`.
- **Proof** (indirect): `companion/_proof/loop.test.mjs` drives the whole queue to completion
  (`remaining === 0`) through repeated claim/serve/disposition; `worker/lib/_proof/dialer.test.mjs`
  exercises serve→disposition→advance.

## How to reapply it
1. **Migration.** A queue table keyed by `(partition, item_id)` — the partition scopes a batch
   (a day, a campaign, a run); use a constant if you don't need batching:
   ```sql
   CREATE TABLE IF NOT EXISTS work_queue (
     partition   TEXT NOT NULL,
     item_id     TEXT NOT NULL,
     position    INTEGER NOT NULL,
     priority    INTEGER,
     status      TEXT NOT NULL DEFAULT 'queued',  -- queued | serving | done | skipped
     claimed_by  TEXT,                             -- worker/user id; NULL = free
     locked_at   TEXT,                             -- ISO time the claim was taken
     PRIMARY KEY (partition, item_id)
   );
   CREATE INDEX IF NOT EXISTS ix_wq_pos   ON work_queue(partition, status, position);
   CREATE INDEX IF NOT EXISTS ix_wq_claim ON work_queue(partition, status, claimed_by);
   ```
2. **Serve-next handler.**
   - First, reclaim: `UPDATE work_queue SET status='queued', claimed_by=NULL WHERE partition=?
     AND status='serving' AND (locked_at IS NULL OR locked_at < ?)` with cutoff `now − N min`.
   - Then read the top-N candidates (`WHERE partition=? AND status='queued' ORDER BY priority,
     position LIMIT 25`) and loop, attempting the claim on each:
     ```js
     const claim = await env.DB.prepare(
       "UPDATE work_queue SET status='serving', claimed_by=?, locked_at=? WHERE partition=? AND item_id=? AND status='queued'")
       .bind(me.id, iso(), part, r.item_id).run().catch(() => ({ meta: { changes: 0 } }));
     if (!claim?.meta || claim.meta.changes < 1) continue;  // someone grabbed it first
     return serve(r);                                        // this row is exclusively ours
     ```
   - If the loop exhausts candidates, report why (`none_available` vs `list_complete`).
3. **Release.** The completion handler flips `serving → done` (or `skipped`); a re-queue path
   flips it back to `queued`, `claimed_by=NULL`.
4. **Remaining/progress counts** must treat `serving` as in-flight, not remaining:
   `remaining = COUNT(status='queued')`.

## Gotchas
- **SQLite has no `SELECT … FOR UPDATE`.** The conditional `UPDATE … WHERE status='queued'` plus
  the rows-changed check IS the lock. Never SELECT a row and then UPDATE it unconditionally —
  two workers will both read `queued` and both proceed.
- **Trust `result.meta.changes`, not your earlier read.** Between listing candidates and firing
  the UPDATE, another worker may have claimed the row; the `WHERE status='queued'` clause is what
  keeps you correct, and `changes < 1` is the signal you lost the race — `continue`, don't retry
  the same row.
- **Loop over enough candidates.** If you only ever attempt row #1, every concurrent worker
  collides on it and all but one fall through with nothing. Pull the top-N (25 in the reference)
  and let each worker settle on a different row.
- **`.catch` the claim UPDATE** to a `{meta:{changes:0}}` shape so a transient DB blip falls
  through to the next candidate instead of throwing out of the whole serve.
- **Stale reclaim is purely time-based** — there is no server-side timer to detect an abandoned
  tab. Too short a cutoff double-serves a slow-but-live worker; too long strands the row. 10 min
  is the reference value; pick it from your real per-item handling time. A row with
  `locked_at IS NULL` is treated as immediately reclaimable.
- **`serving` is a runtime status the original migration comment didn't list** (it said
  `queued | done | skipped`). The code introduces it; audit every COUNT/aggregate so `serving`
  isn't miscounted as remaining or as done.
- **Partition-scope your indexes and queries.** Every hot query filters on `(partition, status,
  …)`; without the composite index the reclaim and candidate scans table-scan the whole queue.
