#!/usr/bin/env node
// Offline trainer for the sovereign edge scorer. Runs on the operator's machine
// (or a scheduled job), NEVER in the request path. Reads a JSON array of labeled
// samples exported from the CRM, fits a logistic model with an honest held-out
// split, prints the metrics, and writes a small weights.json you ship to the
// Worker. Retrain on a cadence (weekly/monthly) as outcomes accrue.
//
//   node train.mjs samples.json weights.json
//
// samples.json: [{ "features": { "days_old": 3, "touches": 2, ... }, "label": 0|1 }, ...]
// Feature EXTRACTORS (row -> features) live in the Worker; export the extracted
// features + the realized outcome (converted? churned? reordered?) as the label.
import { readFileSync, writeFileSync } from 'node:fs';
import { trainLogistic, evaluate } from './score.mjs';

const [, , samplesPath, outPath = 'weights.json'] = process.argv;
if (!samplesPath) { console.error('usage: node train.mjs <samples.json> [weights.json]'); process.exit(2); }

const samples = JSON.parse(readFileSync(samplesPath, 'utf8'));
if (!Array.isArray(samples) || !samples.length) { console.error('samples.json must be a non-empty array'); process.exit(2); }
const featureNames = Object.keys(samples[0].features);

// shuffle deterministically, hold out 20% for honest metrics
let seed = 1337; const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const shuffled = [...samples].sort(() => rnd() - 0.5);
const cut = Math.floor(shuffled.length * 0.8);
const train = shuffled.slice(0, cut);
const test = shuffled.slice(cut);

const model = trainLogistic(train, featureNames, { epochs: 600, lr: 0.2, l2: 1e-3 });
const m = evaluate(model, test);
model.meta.metrics = { auc: +m.auc.toFixed(3), acc: +m.acc.toFixed(3), precision: +m.precision.toFixed(3), recall: +m.recall.toFixed(3), heldOut: test.length };

console.log(`trained on ${train.length}, tested on ${test.length}`);
console.log(`  AUC=${m.auc.toFixed(3)}  acc=${m.acc.toFixed(3)}  precision=${m.precision.toFixed(3)}  recall=${m.recall.toFixed(3)}`);
console.log('  weights:', Object.fromEntries(featureNames.map((f) => [f, +model.weights[f].toFixed(3)])));
if (m.auc < 0.65) console.warn('  ⚠ AUC < 0.65 — weak signal; add features or more labeled outcomes before relying on this score.');

writeFileSync(outPath, JSON.stringify(model, null, 2));
console.log(`wrote ${outPath} (${JSON.stringify(model).length} bytes)`);
