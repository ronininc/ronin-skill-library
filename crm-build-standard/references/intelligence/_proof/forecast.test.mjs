// Proof: the forecaster recovers a known demand rate from a ledger, predicts the
// stockout horizon, fires the reorder signal only when stock is low, and ranks a
// fast mover above a slow one. Deterministic synthetic ledgers.
import assert from 'node:assert/strict';
import { dailyConsumption, ewma, forecastReorder, rankHotSet } from '../forecast.mjs';

const DAY = 86_400_000;
const now = Date.now();
let passed = 0;
const ok = (name, cond, extra = '') => { assert.ok(cond, `FAIL: ${name} ${extra}`); passed++; console.log(`  ✓ ${name}${extra ? ' — ' + extra : ''}`); };

// build a ledger: ~10 units/day (10_000 milli-units) consumed for 30 days, minus a couple restocks
function steadyLedger(ratePerDay, days, jitter = 0) {
  const rnd = (() => { let a = 7; return () => (a = (a * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff; })();
  const entries = [];
  for (let d = days; d >= 1; d--) {
    const qty = ratePerDay * (1 + (jitter ? (rnd() - 0.5) * jitter : 0));
    entries.push({ delta_mu: -Math.round(qty), at: now - d * DAY + 3600_000, reason: 'sale' });
  }
  entries.push({ delta_mu: +50_000, at: now - 15 * DAY, reason: 'restock' }); // inflow ignored by demand calc
  return entries;
}

console.log('\n[1] recovers a known daily demand rate from the ledger');
const ledger = steadyLedger(10_000, 30, 0.1);        // 10 units/day, ±10% jitter
const series = dailyConsumption(ledger, { now });
ok('consumption series has ~30 days', series.length >= 29 && series.length <= 31, `len=${series.length}`);
const { level, trend } = ewma(series);
ok('EWMA recovers ~10 units/day', Math.abs((level + trend) - 10_000) < 1_500, `demand=${Math.round(level + trend)}mu`);
ok('inflow (restock) excluded from demand', series.every((v) => v >= 0));

console.log('\n[2] stockout horizon + reorder signal');
const low = forecastReorder(ledger, { onHandMu: 25_000, leadTimeDays: 7, safetyDays: 3, now });
ok('daily demand ~10 units', Math.abs(low.dailyDemandMu - 10_000) < 1_500, `${Math.round(low.dailyDemandMu)}mu/day`);
ok('predicts stockout ~2.5 days out', low.daysToStockout > 1.5 && low.daysToStockout < 3.5, `${low.daysToStockout}d`);
ok('reorders NOW when on-hand < lead+safety demand', low.reorderNow === true);
ok('recommends a positive reorder qty', low.recommendedQtyMu > 0, `${low.recommendedQtyMu}mu`);

const high = forecastReorder(ledger, { onHandMu: 500_000, leadTimeDays: 7, safetyDays: 3, now });
ok('does NOT reorder when well-stocked', high.reorderNow === false, `daysToStockout=${high.daysToStockout}`);

console.log('\n[3] hot-set velocity ranking puts the fast mover on top');
const items = [
  { id: 'slow-sku', ledger: steadyLedger(1_000, 20), marginCents: 500 },
  { id: 'fast-sku', ledger: steadyLedger(20_000, 20), marginCents: 200 },
  { id: 'dead-sku', ledger: [{ delta_mu: -1000, at: now - 200 * DAY }], marginCents: 900 },
];
const ranked = rankHotSet(items, { now });
ok('fast mover ranks #1', ranked[0].id === 'fast-sku', `order: ${ranked.map((r) => r.id).join(' > ')}`);
ok('dead SKU ranks last', ranked[ranked.length - 1].id === 'dead-sku');
ok('ranking exposes its factors (explainable)', ranked[0].factors && 'velocity' in ranked[0].factors);

console.log(`\nPASS — ${passed} assertions passed\n`);
