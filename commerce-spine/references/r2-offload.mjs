// commerce-spine — R2 offload for CRM media (the 2 MB row-cap escape)
//
// D1 caps any string/BLOB/row at 2 MB, so call recordings, attachments, images,
// and long email HTML CANNOT live inline — and even sub-2 MB blobs burn shard
// budget fast. They go to R2; D1 keeps only a `media_objects` pointer, co-located
// (via the shard router) on the SAME shard as the owning customer/order/product.
//
// Depends on: a shard ShardRouter (crm-shard-router.mjs) and an R2 bucket binding
// (env.MEDIA). Both are plain Cloudflare bindings — no other deps.

const enc = new TextEncoder();

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Store bytes in R2 and write the pointer row into the owner's shard.
 * @param {object}   deps
 * @param {object}   deps.env       Worker env (needs the R2 bucket binding)
 * @param {ShardRouter} deps.router
 * @param {string}   [deps.bucket]  R2 binding name (default 'MEDIA')
 * @param {object}   obj
 * @param {string}   obj.tenantId
 * @param {string}   obj.ownerKind  'customer' | 'order' | 'customer_event' | 'product' | …
 * @param {string}   obj.ownerId    the aggregate-root id it co-locates with (customer_id / product_id)
 * @param {string}   [obj.ownerDomain] shard domain of the owner (default 'customer')
 * @param {ArrayBuffer|Uint8Array} obj.bytes
 * @param {string}   [obj.contentType]
 * @param {object}   [obj.meta]     small metadata (caption/source) — encrypt before calling if sensitive
 * @returns {Promise<{media_id, r2_key, byte_len, sha256}>}
 */
export async function putMedia({ env, router, bucket = 'MEDIA' }, obj) {
  const bytes = obj.bytes instanceof Uint8Array ? obj.bytes : new Uint8Array(obj.bytes);
  const sha = await sha256Hex(bytes);
  const mediaId = `${obj.tenantId}:media:${sha.slice(0, 24)}`;
  // Key layout mirrors the shard doctrine: tenant/owner-scoped, content-addressed.
  const r2Key = `${obj.tenantId}/${obj.ownerKind}/${obj.ownerId}/${sha}`;

  const store = env[bucket];
  if (!store) throw new Error(`r2-offload: env has no R2 binding '${bucket}' — add it to wrangler.jsonc`);
  await store.put(r2Key, bytes, {
    httpMetadata: obj.contentType ? { contentType: obj.contentType } : undefined,
  });

  // Pointer row lands on the SAME shard as the owner (co-located), via the router.
  const db = await router.dbFor('media_objects', {
    tenant_id: obj.tenantId, owner_id: obj.ownerId, owner_domain: obj.ownerDomain || 'customer',
  });
  await db.prepare(
    `INSERT OR REPLACE INTO media_objects
     (media_id, tenant_id, owner_kind, owner_id, r2_key, content_type, byte_len, sha256, meta_json, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    mediaId, obj.tenantId, obj.ownerKind, obj.ownerId, r2Key,
    obj.contentType || null, bytes.byteLength, sha,
    obj.meta ? JSON.stringify(obj.meta) : null, Date.now()
  ).run();

  return { media_id: mediaId, r2_key: r2Key, byte_len: bytes.byteLength, sha256: sha };
}

/** List an owner's media pointers (single-shard read — owner is one root). */
export async function listMedia({ router }, { tenantId, ownerKind, ownerId, ownerDomain = 'customer' }) {
  const db = await router.dbFor('media_objects', { tenant_id: tenantId, owner_id: ownerId, owner_domain: ownerDomain });
  const { results } = await db
    .prepare('SELECT * FROM media_objects WHERE owner_kind = ? AND owner_id = ? ORDER BY created_at DESC')
    .bind(ownerKind, ownerId).all();
  return results;
}

/** Fetch the bytes for one pointer from R2. */
export async function getMediaBytes({ env, bucket = 'MEDIA' }, r2Key) {
  const store = env[bucket];
  const object = await store.get(r2Key);
  return object ? await object.arrayBuffer() : null;
}
