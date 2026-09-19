// WORKFORCE PRODUCTIVITY — pure compute (Worker/Node, zero deps).
// Mirrors TSS server/src/runtime/crm-workforce-productivity.ts (the canonical source). Copy into the
// client CRM's worker/lib/. Turns a flat list of REAL CRM work events into the admin's live
// "who's working, who's not" dataset. Activity-derived only — NEVER keystroke/screen surveillance.

export const DEFAULT_ACTIVITY_WEIGHTS = {
  lead_added: 2, note_filed: 3, note_dispatched: 3, message_sent: 2,
  deal_updated: 4, queue_action: 1, login: 0.5, custom: 1,
};
export const DEFAULT_PRESENCE_THRESHOLDS = { activeMinutes: 15, idleMinutes: 120 };

const HOUR_MS = 3_600_000, DAY_MS = 86_400_000;
const STATUS_RANK = { active: 0, idle: 1, offline: 2 };

function resolveWeight(kind, evWeight, weights) {
  if (typeof evWeight === 'number' && Number.isFinite(evWeight)) return evWeight;
  const w = weights[kind];
  if (typeof w === 'number' && Number.isFinite(w)) return w;
  const d = DEFAULT_ACTIVITY_WEIGHTS[kind];
  return typeof d === 'number' ? d : 1;
}

/**
 * events: [{ employeeId, employeeName, kind, weight?, occurredAt(ISO) }]
 * options: { now?:Date, windowDays?:number, weights?, thresholds?, roster?:[{employeeId,employeeName}] }
 * → { generatedAt, windowDays, team{...}, employees[...] } (working-first ordering)
 */
export function computeWorkforceProductivity(events, options = {}) {
  const now = options.now ?? new Date();
  const nowMs = now.getTime();
  const windowDays = Math.max(1, Math.floor(options.windowDays ?? 7));
  const weights = options.weights ?? {};
  const thresholds = options.thresholds ?? DEFAULT_PRESENCE_THRESHOLDS;
  const windowStartMs = nowMs - windowDays * DAY_MS;
  const todayStartMs = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());

  const byEmp = new Map();
  const ensure = (id, name) => {
    let a = byEmp.get(id);
    if (!a) { a = { employeeId: id, employeeName: name, lastMs: null, eventsToday: 0, weightedToday: 0, weightedWindow: 0, byKind: {}, activeHourBuckets: new Set() }; byEmp.set(id, a); }
    else if (name && a.employeeName !== name) a.employeeName = name;
    return a;
  };

  // Roster seeds zero-activity employees so "who's NOT working" is visible (offline, 0).
  for (const r of options.roster ?? []) ensure(r.employeeId, r.employeeName);

  for (const ev of events) {
    const t = Date.parse(ev.occurredAt);
    if (!Number.isFinite(t) || t < windowStartMs || t > nowMs) continue;
    const a = ensure(ev.employeeId, ev.employeeName);
    const w = resolveWeight(ev.kind, ev.weight, weights);
    a.weightedWindow += w;
    a.byKind[ev.kind] = (a.byKind[ev.kind] ?? 0) + 1;
    a.activeHourBuckets.add(Math.floor(t / HOUR_MS));
    if (a.lastMs === null || t > a.lastMs) a.lastMs = t;
    if (t >= todayStartMs) { a.eventsToday += 1; a.weightedToday += w; }
  }

  const employees = [...byEmp.values()].map((a) => {
    const minutesSinceActive = a.lastMs === null ? null : Math.max(0, Math.round((nowMs - a.lastMs) / 60_000));
    const status = minutesSinceActive === null ? 'offline'
      : minutesSinceActive <= thresholds.activeMinutes ? 'active'
      : minutesSinceActive <= thresholds.idleMinutes ? 'idle' : 'offline';
    const activeHours = a.activeHourBuckets.size;
    const ratePerActiveHour = activeHours > 0 ? Math.round((a.weightedWindow / activeHours) * 100) / 100 : 0;
    const priorDays = Math.max(1, windowDays - 1);
    const priorAvg = (a.weightedWindow - a.weightedToday) / priorDays;
    const trend = priorAvg <= 0 ? (a.weightedToday > 0 ? 'up' : 'flat')
      : a.weightedToday > priorAvg * 1.15 ? 'up'
      : a.weightedToday < priorAvg * 0.85 ? 'down' : 'flat';
    return {
      employeeId: a.employeeId, employeeName: a.employeeName, status,
      lastActiveAt: a.lastMs === null ? null : new Date(a.lastMs).toISOString(),
      minutesSinceActive, eventsToday: a.eventsToday,
      weightedToday: Math.round(a.weightedToday * 100) / 100,
      weightedWindow: Math.round(a.weightedWindow * 100) / 100,
      ratePerActiveHour, byKind: a.byKind, trend,
    };
  });

  employees.sort((x, y) =>
    STATUS_RANK[x.status] - STATUS_RANK[y.status]
    || y.weightedToday - x.weightedToday
    || y.weightedWindow - x.weightedWindow
    || x.employeeName.localeCompare(y.employeeName));

  const team = {
    totalEmployees: employees.length,
    activeNow: employees.filter((e) => e.status === 'active').length,
    idle: employees.filter((e) => e.status === 'idle').length,
    offline: employees.filter((e) => e.status === 'offline').length,
    eventsToday: employees.reduce((s, e) => s + e.eventsToday, 0),
    weightedToday: Math.round(employees.reduce((s, e) => s + e.weightedToday, 0) * 100) / 100,
    weightedWindow: Math.round(employees.reduce((s, e) => s + e.weightedWindow, 0) * 100) / 100,
  };
  return { generatedAt: now.toISOString(), windowDays, team, employees };
}
