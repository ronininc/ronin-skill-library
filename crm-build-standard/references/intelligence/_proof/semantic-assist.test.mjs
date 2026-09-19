// Proof (wiring + logic + governance) for the two edge-model modules. The real
// embedding/LLM QUALITY needs a Cloudflare deploy, but everything that is OURS —
// how we call the bindings, the similarity/dedup ranking, tenant filtering, and
// the hard "assist never sends on its own" governance rule — is proven here with
// an injected mock `env` (a deterministic local embedder + a canned LLM + an
// in-memory Vectorize). If the wiring or governance regresses, this goes red.
import assert from 'node:assert/strict';
import { indexEntity, findSimilar, findDuplicate, recommend, cosine } from '../semantic.mjs';
import { summarize, draftReply, classify, extractFields } from '../assist.mjs';

let passed = 0;
const ok = (name, cond, extra = '') => { assert.ok(cond, `FAIL: ${name} ${extra}`); passed++; console.log(`  ✓ ${name}${extra ? ' — ' + extra : ''}`); };

// deterministic local embedder: char-3gram bag hashed into 64 dims → similar
// strings get similar vectors (enough to prove ranking, not to prove CF quality)
function localEmbed(s) {
  const v = new Array(64).fill(0);
  const t = ` ${String(s).toLowerCase().replace(/[^a-z0-9]+/g, ' ')} `;
  for (let i = 0; i < t.length - 2; i++) {
    let h = 0; for (let k = 0; k < 3; k++) h = (h * 31 + t.charCodeAt(i + k)) >>> 0;
    v[h % 64] += 1;
  }
  return v;
}

const calls = [];
function makeEnv() {
  const store = [];
  return {
    AI: {
      async run(model, input) {
        calls.push(model);
        if (model.includes('bge')) return { data: input.text.map(localEmbed) };
        // canned LLM: echo a deterministic "response" so we test wiring, not quality
        const last = input.messages[input.messages.length - 1].content;
        if (input.messages[0].content.includes('exactly one label')) return { response: '{"label":"support","urgency":"high","confidence":0.9}' };
        if (input.messages[0].content.includes('Extract these fields')) return { response: '{"name":"Ana","phone":"555-0100"}' };
        return { response: `SUMMARY: ${last.slice(0, 40)}` };
      },
    },
    VECTORIZE: {
      async upsert(rows) { for (const r of rows) { const i = store.findIndex((x) => x.id === r.id); if (i >= 0) store[i] = r; else store.push(r); } },
      async query(vector, { topK = 5, filter, returnMetadata } = {}) {
        let cands = store;
        if (filter) cands = cands.filter((r) => Object.entries(filter).every(([k, val]) => r.metadata?.[k] === val));
        return { matches: cands.map((r) => ({ id: r.id, score: cosine(vector, r.values), metadata: returnMetadata ? r.metadata : undefined }))
          .sort((a, b) => b.score - a.score).slice(0, topK) };
      },
    },
  };
}

async function main() {
  const env = makeEnv();

  console.log('\n[1] semantic index + similarity ranking (real logic, local embeddings)');
  await indexEntity(env, { id: 'c1', text: 'Ana Ruiz car accident rear-ended on I-10', metadata: { tenant_id: 't1', kind: 'lead' } });
  await indexEntity(env, { id: 'c2', text: 'slip and fall grocery store wet floor', metadata: { tenant_id: 't1', kind: 'lead' } });
  await indexEntity(env, { id: 'c3', text: 'other tenant lead', metadata: { tenant_id: 't2', kind: 'lead' } });
  const hits = await findSimilar(env, 'rear-end collision on the freeway, Ana', { topK: 2, filter: { tenant_id: 't1' } });
  ok('most similar lead ranks first', hits[0].id === 'c1', `order: ${hits.map((h) => h.id).join(',')}`);
  ok('tenant filter excludes other tenants', hits.every((h) => h.metadata?.tenant_id === 't1'));

  console.log('\n[2] duplicate detection by threshold');
  const dup = await findDuplicate(env, 'Ana Ruiz rear-ended car accident I-10', { threshold: 0.6, filter: { tenant_id: 't1' } });
  ok('near-duplicate detected above threshold', dup && dup.id === 'c1', `score=${dup?.score?.toFixed(2)}`);
  const noDup = await findDuplicate(env, 'completely unrelated plumbing invoice', { threshold: 0.9, filter: { tenant_id: 't1' } });
  ok('no false-positive duplicate below threshold', noDup === null);

  console.log('\n[3] recommend excludes the seed itself');
  const recs = await recommend(env, 'car accident freeway', { topK: 5, filter: { tenant_id: 't1' }, excludeId: 'c1' });
  ok('recommendations exclude the seed id', recs.every((r) => r.id !== 'c1'));

  console.log('\n[4] GOVERNANCE: assist is advisory and NEVER sends/writes on its own');
  const draft = await draftReply(env, { context: 'lead asked about pricing', goal: 'invite to a call', channel: 'email' });
  ok('draftReply returns requiresApproval', draft.requiresApproval === true);
  ok('draftReply did NOT send (sent=false)', draft.sent === false);
  ok('draftReply produced a draft body', typeof draft.draft === 'string' && draft.draft.length > 0);
  const ext = await extractFields(env, 'call Ana at 555-0100', ['name', 'phone']);
  ok('extractFields requires approval before any CRM write', ext.requiresApproval === true);
  const sum = await summarize(env, { subject: 'lead', facts: { name: 'Ana', status: 'new' } });
  ok('summarize is advisory', sum.advisory === true);

  console.log('\n[5] classify clamps to the allowed vocabulary (no hallucinated labels)');
  const cls = await classify(env, 'my invoice is wrong and I am furious', ['support', 'sales', 'billing']);
  ok('classification stays in-vocabulary', ['support', 'sales', 'billing'].includes(cls.label), `label=${cls.label}`);
  const bad = await classify({ AI: { async run() { return { response: '{"label":"totally_made_up","confidence":0.9}' }; } } }, 'x', ['support', 'sales']);
  ok('out-of-vocabulary label is flagged for review, not trusted', bad.label === null && bad.needsReview === true);

  console.log('\n[6] the right edge models were called');
  ok('embedding model @cf/baai/bge was invoked', calls.some((m) => m.includes('bge')));
  ok('LLM @cf/meta/llama was invoked for assist', calls.some((m) => m.includes('llama')));

  console.log(`\nPASS — ${passed} assertions passed (wiring + logic + governance; model quality requires deploy)\n`);
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1); });
