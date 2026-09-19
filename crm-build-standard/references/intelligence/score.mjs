// CRM Intelligence — sovereign edge scoring engine.
//
// A learned, EXPLAINABLE score that runs as pure JS inside a Cloudflare Worker
// (or the mobile-backend), with NO network call and NO external service. You
// train offline on exported CRM rows (train.mjs), ship the resulting weights as
// a small JSON blob, and score live entities at the edge. Fits the sovereignty
// doctrine: the model is data the operator owns, inference is local math, and
// every score comes with the factors that produced it (no black box).
//
// Model shape (JSON-serializable — this is what you ship):
//   { kind:'logreg', featureNames:[...], mean:{...}, std:{...},
//     weights:{...}, bias, meta:{ label, trainedAt, n, metrics } }
// Feature EXTRACTORS (entity -> numbers) live in worker code, not the model,
// because they read your schema; the model is just the learned coefficients.

const sigmoid = (z) => 1 / (1 + Math.exp(-z));

/** Turn an entity row (+ optional context) into a flat {name:number} vector via
 *  a declarative extractor map. Each extractor returns a number (booleans → 0/1,
 *  missing → 0). Keep extractors pure and cheap — they run per score. */
export function extractFeatures(entity, extractors, ctx = {}) {
  const out = {};
  for (const [name, fn] of Object.entries(extractors)) {
    const v = fn(entity, ctx);
    out[name] = typeof v === 'boolean' ? (v ? 1 : 0) : Number.isFinite(v) ? v : 0;
  }
  return out;
}

/** Standardization params (z-score) computed from a training matrix. */
function fitStandardizer(rows, featureNames) {
  const mean = {}, std = {};
  for (const f of featureNames) {
    const xs = rows.map((r) => r.features[f] ?? 0);
    const m = xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
    const v = xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length || 1);
    mean[f] = m;
    std[f] = Math.sqrt(v) || 1; // guard zero-variance features
  }
  return { mean, std };
}

/**
 * Train a logistic-regression scorer with gradient descent + L2. Pure JS,
 * deterministic given the data. Returns a JSON-serializable model.
 * @param {{features:Record<string,number>, label:0|1}[]} samples
 * @param {string[]} featureNames
 */
export function trainLogistic(samples, featureNames, opts = {}) {
  const { epochs = 400, lr = 0.1, l2 = 1e-3 } = opts;
  const { mean, std } = fitStandardizer(samples, featureNames);
  const z = (r) => featureNames.map((f) => ((r.features[f] ?? 0) - mean[f]) / std[f]);
  const X = samples.map(z);
  const y = samples.map((r) => r.label);
  const w = new Array(featureNames.length).fill(0);
  let b = 0;
  const n = X.length || 1;
  for (let e = 0; e < epochs; e++) {
    const gw = new Array(featureNames.length).fill(0);
    let gb = 0;
    for (let i = 0; i < X.length; i++) {
      const p = sigmoid(X[i].reduce((s, xj, j) => s + xj * w[j], b));
      const err = p - y[i];
      for (let j = 0; j < w.length; j++) gw[j] += err * X[i][j];
      gb += err;
    }
    for (let j = 0; j < w.length; j++) w[j] -= lr * (gw[j] / n + l2 * w[j]);
    b -= lr * (gb / n);
  }
  const weights = {};
  featureNames.forEach((f, j) => { weights[f] = w[j]; });
  return {
    kind: 'logreg', featureNames, mean, std, weights, bias: b,
    meta: { trainedAt: new Date().toISOString(), n: samples.length },
  };
}

export class Scorer {
  /** @param {object} model a model produced by trainLogistic (or its JSON) */
  constructor(model) {
    if (!model || model.kind !== 'logreg') throw new Error('Scorer: unsupported model');
    this.model = model;
  }

  /**
   * Score a feature vector. Returns the probability, a label at `threshold`,
   * and the ranked factors (signed contributions) that produced it — so the CRM
   * can SHOW an agent WHY, never just a number.
   * @param {Record<string,number>} features
   */
  score(features, threshold = 0.5) {
    const { featureNames, mean, std, weights, bias } = this.model;
    let logit = bias;
    const factors = [];
    for (const f of featureNames) {
      const z = (((features[f] ?? 0) - mean[f]) / std[f]);
      const contribution = weights[f] * z;
      logit += contribution;
      factors.push({ feature: f, value: features[f] ?? 0, z, contribution });
    }
    factors.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
    const p = sigmoid(logit);
    return {
      p,
      label: p >= threshold ? 1 : 0,
      topFactors: factors.slice(0, 5),
      factors,
      modelTrainedAt: this.model.meta?.trainedAt,
    };
  }
}

// ── evaluation helpers (used by the trainer + proof, not at inference) ───────
export function evaluate(model, samples, threshold = 0.5) {
  const scorer = new Scorer(model);
  let tp = 0, tn = 0, fp = 0, fn = 0;
  const scored = samples.map((s) => ({ p: scorer.score(s.features, threshold).p, y: s.label }));
  for (const { p, y } of scored) {
    const yhat = p >= threshold ? 1 : 0;
    if (yhat === 1 && y === 1) tp++;
    else if (yhat === 0 && y === 0) tn++;
    else if (yhat === 1 && y === 0) fp++;
    else fn++;
  }
  const acc = (tp + tn) / (samples.length || 1);
  // AUC via Mann–Whitney U (rank-based), robust for a proof.
  const pos = scored.filter((s) => s.y === 1).map((s) => s.p);
  const neg = scored.filter((s) => s.y === 0).map((s) => s.p);
  let wins = 0;
  for (const pp of pos) for (const nn of neg) wins += pp > nn ? 1 : pp === nn ? 0.5 : 0;
  const auc = pos.length && neg.length ? wins / (pos.length * neg.length) : 0.5;
  return { acc, auc, tp, tn, fp, fn, precision: tp / (tp + fp || 1), recall: tp / (tp + fn || 1) };
}
