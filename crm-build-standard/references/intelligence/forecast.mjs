// CRM Intelligence — forecasting off the append-only ledgers.
//
// Pure JS, sovereign, explainable. Turns an inventory/consumption/valuation
// ledger into a forward view: expected daily demand, days-to-stockout, a reorder
// signal, and a velocity rank for the POS hot-set. No external service.
//
// Method: EWMA (exponentially-weighted moving average) of recent per-day
// consumption for the level, plus a light trend term. EWMA is the right default
// for CRM demand — it's robust on short, spiky series, needs no seasonality
// assumption, and is trivially explainable ("recent days weighted heaviest").

/** Bucket signed ledger deltas into per-day consumption (negative deltas = sold/used). */
export function dailyConsumption(entries, { valueKey = 'delta_mu', timeKey = 'at', now = Date.now() } = {}) {
  const DAY = 86_400_000;
  const byDay = new Map();
  let minDay = Infinity, maxDay = -Infinity;
  for (const e of entries) {
    const delta = Number(e[valueKey] ?? 0);
    if (delta >= 0) continue;                    // only consumption (outflow)
    const day = Math.floor(Number(e[timeKey]) / DAY);
    byDay.set(day, (byDay.get(day) || 0) + Math.abs(delta));
    if (day < minDay) minDay = day;
    if (day > maxDay) maxDay = day;
  }
  if (!Number.isFinite(minDay)) return [];
  // Fill gaps WITHIN the observed consumption span only. Deliberately excludes
  // the current (incomplete) day — counting today's partial zero as a full day
  // biases demand downward. Genuine zero-sale days between real sales still fill.
  const series = [];
  for (let d = minDay; d <= maxDay; d++) series.push(byDay.get(d) || 0);
  return series;
}

/** EWMA level + trend of a numeric series. alpha weights recency. */
export function ewma(series, alpha = 0.3) {
  if (!series.length) return { level: 0, trend: 0 };
  let level = series[0];
  let trend = 0;
  for (let i = 1; i < series.length; i++) {
    const prev = level;
    level = alpha * series[i] + (1 - alpha) * level;
    trend = 0.2 * (level - prev) + 0.8 * trend; // smoothed slope
  }
  return { level, trend };
}

/**
 * Reorder forecast for one SKU from its inventory ledger.
 * @returns {{ dailyDemandMu, daysToStockout, reorderNow, recommendedQtyMu, basis }}
 */
export function forecastReorder(ledgerEntries, opts = {}) {
  const {
    onHandMu = 0, leadTimeDays = 7, reviewDays = 7, safetyDays = 3, alpha = 0.3, now = Date.now(),
  } = opts;
  const series = dailyConsumption(ledgerEntries, { now });
  const { level, trend } = ewma(series, alpha);
  const dailyDemandMu = Math.max(0, level + trend);         // forward daily demand
  const daysToStockout = dailyDemandMu > 0 ? onHandMu / dailyDemandMu : Infinity;
  // Reorder point = demand over (lead time + safety); cover through the next review cycle.
  const reorderPointMu = dailyDemandMu * (leadTimeDays + safetyDays);
  const reorderNow = onHandMu <= reorderPointMu;
  const targetCoverMu = dailyDemandMu * (leadTimeDays + reviewDays + safetyDays);
  const recommendedQtyMu = Math.max(0, Math.round(targetCoverMu - onHandMu));
  return {
    dailyDemandMu,
    daysToStockout: Number.isFinite(daysToStockout) ? Math.round(daysToStockout * 10) / 10 : Infinity,
    reorderNow,
    recommendedQtyMu,
    basis: { level, trend, sampleDays: series.length, reorderPointMu },
  };
}

/**
 * Rank items for the POS "hot-set" by learned velocity — replaces a hand-tuned
 * heuristic with a transparent weighted score over recent velocity, recency, and
 * margin. Weights are data you can tune/learn; the score is explainable.
 * @param {{id:string, ledger:any[], marginCents?:number}[]} items
 */
export function rankHotSet(items, opts = {}) {
  const { weights = { velocity: 1.0, recency: 0.5, margin: 0.3 }, now = Date.now(), topN } = opts;
  const scored = items.map((it) => {
    const series = dailyConsumption(it.ledger || [], { now });
    const { level, trend } = ewma(series);
    const velocity = Math.max(0, level + trend);
    const lastOutflow = (it.ledger || []).filter((e) => Number(e.delta_mu ?? 0) < 0).map((e) => Number(e.at)).sort((a, b) => b - a)[0];
    const recencyDays = lastOutflow ? (now - lastOutflow) / 86_400_000 : 999;
    const recency = 1 / (1 + recencyDays);          // fresher = higher
    const margin = (it.marginCents || 0) / 100;
    const score = weights.velocity * velocity + weights.recency * recency + weights.margin * Math.log1p(margin);
    return { id: it.id, score, factors: { velocity, recency, margin } };
  });
  scored.sort((a, b) => b.score - a.score);
  return topN ? scored.slice(0, topN) : scored;
}
