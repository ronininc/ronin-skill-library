// A minimal Cloudflare-D1-compatible facade over node:sqlite (node >= 22.5).
// Lets the real worker/lib modules (crm-shard-router.mjs, r2-offload.mjs) run
// UNMODIFIED against local .db files — the honest way to prove routing logic
// without deploying. Mirrors the subset of the D1 API the router uses:
//   db.prepare(sql).bind(...args).first() / .all() / .run()
import { DatabaseSync } from 'node:sqlite';

class D1Prepared {
  constructor(db, sql) { this.db = db; this.sql = sql; this.args = []; }
  bind(...args) { this.args = args; return this; }
  first() {
    const row = this.db.prepare(this.sql).get(...this.args);
    return row === undefined ? null : row;            // D1 returns null, not undefined
  }
  all() {
    const results = this.db.prepare(this.sql).all(...this.args);
    return { results, success: true, meta: {} };
  }
  run() {
    const info = this.db.prepare(this.sql).run(...this.args);
    return { success: true, meta: { changes: info.changes, last_row_id: info.lastInsertRowid } };
  }
}

class D1Database {
  constructor(path) { this._db = new DatabaseSync(path); }
  prepare(sql) { return new D1Prepared(this._db, sql); }
  exec(sql) { this._db.exec(sql); return { count: 0 }; }
  raw() { return this._db; }
}

export function openD1(path = ':memory:') { return new D1Database(path); }

// A tiny in-process R2 stand-in with the .put/.get shape r2-offload.mjs uses.
export function fakeR2() {
  const store = new Map();
  return {
    _store: store,
    async put(key, bytes /*, opts */) { store.set(key, new Uint8Array(bytes)); },
    async get(key) {
      if (!store.has(key)) return null;
      const bytes = store.get(key);
      return { async arrayBuffer() { return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength); } };
    },
  };
}
