// Proof: the sovereign edge scorer actually LEARNS a signal and EXPLAINS it —
// not just "runs". Deterministic (seeded) synthetic lead-conversion data, an
// honest train/held-out-test split, and bars on held-out AUC + accuracy. Then it
// asserts the explanation (top factors) tracks the real generative signal, and
// that inference is pure/serializable (round-trips through JSON like a shipped
// weights blob).
import assert from 'node:assert/strict';
import { trainLogistic, Scorer, evaluate, extractFeatures } from '../score.mjs';

// deterministic RNG so the proof is reproducible
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(42);
const sig = (z) => 1 / (1 + Math.exp(-z));

// The TRUE generative model of "did this lead convert" (unknown to the scorer):
// fresh leads, more touches, having a phone, and a high-intent source convert;
// cold/no-contact leads don't. Noise added so it isn't separable.
const FEATURES = ['days_old', 'touches', 'has_phone', 'has_email', 'high_intent', 'prior_deals'];
function makeLead() {
  const days_old = Math.floor(rnd() * 30);
  const touches = Math.floor(rnd() * 6);
  const has_phone = rnd() < 0.6 ? 1 : 0;
  const has_email = rnd() < 0.7 ? 1 : 0;
  const high_intent = rnd() < 0.4 ? 1 : 0;
  const prior_deals = rnd() < 0.2 ? Math.floor(rnd() * 3) : 0;
  const trueLogit =
    -0.9
    - 0.08 * days_old
    + 0.45 * touches
    + 0.8 * has_phone
    + 0.2 * has_email
    + 1.1 * high_intent
    + 0.6 * prior_deals
    + (rnd() - 0.5) * 0.5; // irreducible noise (realistic learnable signal-to-noise)
  const label = rnd() < sig(trueLogit) ? 1 : 0;
  return { features: { days_old, touches, has_phone, has_email, high_intent, prior_deals }, label };
}

let passed = 0;
const ok = (name, cond, extra = '') => { assert.ok(cond, `FAIL: ${name} ${extra}`); passed++; console.log(`  ✓ ${name}${extra ? ' — ' + extra : ''}`); };

const data = Array.from({ length: 4000 }, makeLead); // large enough for a stable held-out AUC
const train = data.slice(0, 3000);
const test = data.slice(3000);

console.log('\n[1] the model learns a real signal (held-out test, never seen in training)');
const model = trainLogistic(train, FEATURES, { epochs: 600, lr: 0.2, l2: 1e-3 });
const evalTest = evaluate(model, test);
ok('held-out AUC beats the bar', evalTest.auc > 0.80, `AUC=${evalTest.auc.toFixed(3)}`);
ok('held-out accuracy beats the bar', evalTest.acc > 0.70, `acc=${evalTest.acc.toFixed(3)}`);
ok('a positive base-rate exists (not degenerate)', test.some((t) => t.label === 1) && test.some((t) => t.label === 0));

console.log('\n[2] learned weights recover the SIGN of the true drivers (sanity of learning)');
ok('high_intent is a positive driver', model.weights.high_intent > 0, `w=${model.weights.high_intent.toFixed(2)}`);
ok('touches is a positive driver', model.weights.touches > 0, `w=${model.weights.touches.toFixed(2)}`);
ok('days_old is a negative driver (staleness hurts)', model.weights.days_old < 0, `w=${model.weights.days_old.toFixed(2)}`);

console.log('\n[3] explainability: a hot lead scores high AND names the right reasons');
const scorer = new Scorer(model);
const hot = extractFeatures(
  { created_ago: 1, contacts: 5, phone: '555', email: 'a@b.c', source: 'web_form', deals: 2 },
  {
    days_old: (e) => e.created_ago,
    touches: (e) => e.contacts,
    has_phone: (e) => !!e.phone,
    has_email: (e) => !!e.email,
    high_intent: (e) => (e.source === 'web_form' ? 1 : 0),
    prior_deals: (e) => e.deals,
  },
);
const hotScore = scorer.score(hot);
ok('hot lead scores high', hotScore.p > 0.75, `p=${hotScore.p.toFixed(2)}`);
const topPositive = hotScore.topFactors.filter((f) => f.contribution > 0).map((f) => f.feature);
ok('top positive factors include a true driver', topPositive.some((f) => ['high_intent', 'touches', 'prior_deals', 'has_phone'].includes(f)), `top+: ${topPositive.join(',')}`);

const cold = extractFeatures(
  { created_ago: 27, contacts: 0, phone: '', email: '', source: 'purchased_list', deals: 0 },
  {
    days_old: (e) => e.created_ago,
    touches: (e) => e.contacts,
    has_phone: (e) => !!e.phone,
    has_email: (e) => !!e.email,
    high_intent: (e) => (e.source === 'web_form' ? 1 : 0),
    prior_deals: (e) => e.deals,
  },
);
const coldScore = scorer.score(cold);
ok('cold lead scores low', coldScore.p < 0.35, `p=${coldScore.p.toFixed(2)}`);
ok('hot ranks above cold', hotScore.p > coldScore.p);

console.log('\n[4] the model is a shippable JSON weights blob (pure, serializable)');
const shipped = JSON.parse(JSON.stringify(model)); // round-trip like a weights.json artifact
const reloaded = new Scorer(shipped);
ok('reloaded model scores identically', Math.abs(reloaded.score(hot).p - hotScore.p) < 1e-12);
ok('weights blob is small', JSON.stringify(shipped).length < 4000, `${JSON.stringify(shipped).length} bytes`);

console.log(`\nPASS — ${passed} assertions passed (held-out AUC ${evalTest.auc.toFixed(3)}, acc ${evalTest.acc.toFixed(3)})\n`);
