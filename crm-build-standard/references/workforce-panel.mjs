// WORKFORCE PRODUCTIVITY — framework-neutral view core (browser, zero deps).
// Mirrors TSS app/src/dashboard/components/workforce-panel.ts (canonical). Copy into the client CRM's
// public/ and include with <script type="module">. Renders GET /api/workforce; polls. DOM + fetch only.

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function ago(minutes) {
  if (minutes === null || minutes === undefined) return 'no activity';
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}h ago`;
  return `${Math.round(minutes / 1440)}d ago`;
}
const STATUS_LABEL = { active: 'Working', idle: 'Idle', offline: 'Offline' };
const TREND_MARK = { up: '▲', flat: '▬', down: '▼' };

export function renderWorkforcePanelHTML(dataset, opts = {}) {
  const title = esc(opts.title ?? 'Workforce · who’s working now');
  if (opts.error) return `<div class="wfp-root"><div class="wfp-head"><span class="wfp-title">${title}</span></div><div class="wfp-empty">Couldn’t load — ${esc(opts.error)}</div></div>`;
  if (!dataset) return `<div class="wfp-root"><div class="wfp-head"><span class="wfp-title">${title}</span></div><div class="wfp-empty">Loading…</div></div>`;
  const t = dataset.team;
  const rows = (dataset.employees || []).length ? dataset.employees.map((e) => {
    const kinds = Object.entries(e.byKind || {}).sort((a, b) => b[1] - a[1]).slice(0, 3)
      .map(([k, n]) => `<span class="wfp-kind">${esc(k.replace(/_/g, ' '))} ${n}</span>`).join('');
    return `<div class="wfp-row wfp-${e.status}"><span class="wfp-dot"></span><span class="wfp-name">${esc(e.employeeName)}</span><span class="wfp-status">${STATUS_LABEL[e.status]}<span class="wfp-since">${esc(ago(e.minutesSinceActive))}</span></span><span class="wfp-score">${e.weightedToday}<span class="wfp-lbl">today</span></span><span class="wfp-rate">${e.ratePerActiveHour}<span class="wfp-lbl">/active hr</span></span><span class="wfp-trend wfp-t-${e.trend}">${TREND_MARK[e.trend]}</span><span class="wfp-kinds">${kinds}</span></div>`;
  }).join('') : `<div class="wfp-empty">No employees on this CRM yet.</div>`;
  return `<div class="wfp-root"><div class="wfp-head"><span class="wfp-title">${title}</span><span class="wfp-team"><b class="wfp-active">${t.activeNow}</b> working · <b class="wfp-idleN">${t.idle}</b> idle · <b class="wfp-offN">${t.offline}</b> offline · <b>${t.weightedToday}</b> work today<span class="wfp-win">last ${dataset.windowDays}d</span></span></div><div class="wfp-list">${rows}</div><div class="wfp-foot">Activity-derived from real CRM work — updated ${esc(new Date(dataset.generatedAt).toLocaleTimeString())}. Not screen/keystroke tracking.</div></div>`;
}

export const WORKFORCE_PANEL_CSS = `
.wfp-root{--wfp-void:#0a0908;--wfp-panel:#15110d;--wfp-line:#2c241c;--wfp-ash:#e2dacb;--wfp-mut:#93887a;--wfp-faint:#5f574c;--wfp-brass:#c69a52;--wfp-jade:#4fa07b;--wfp-gold:#e7b657;--wfp-blood:#c22530;font-family:system-ui,sans-serif;color:var(--wfp-ash);background:linear-gradient(180deg,var(--wfp-panel),var(--wfp-void));border:1px solid var(--wfp-line);border-radius:8px;overflow:hidden}
.wfp-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--wfp-line)}
.wfp-title{font-family:'Special Elite',ui-serif,Georgia,serif;font-size:.92rem;color:var(--wfp-brass)}
.wfp-team{font-size:.74rem;color:var(--wfp-mut)}.wfp-team b{font-variant-numeric:tabular-nums;color:var(--wfp-ash)}
.wfp-team .wfp-active{color:var(--wfp-jade)}.wfp-team .wfp-idleN{color:var(--wfp-gold)}.wfp-team .wfp-offN{color:var(--wfp-faint)}
.wfp-win{margin-left:8px;font-size:.6rem;text-transform:uppercase;letter-spacing:.12em;color:var(--wfp-faint)}
.wfp-list{max-height:360px;overflow:auto}
.wfp-row{display:grid;grid-template-columns:14px 1.4fr .9fr auto auto 20px 1.3fr;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--wfp-line)}
.wfp-row:last-child{border-bottom:none}
.wfp-dot{width:9px;height:9px;border-radius:50%;background:var(--wfp-faint)}
.wfp-active .wfp-dot{background:var(--wfp-jade);box-shadow:0 0 8px var(--wfp-jade)}
.wfp-idle .wfp-dot{background:var(--wfp-gold)}.wfp-offline .wfp-dot{background:var(--wfp-faint)}
.wfp-name{font-family:'Barlow Condensed','Arial Narrow',sans-serif;font-weight:600;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wfp-status{font-size:.72rem;color:var(--wfp-mut);display:flex;flex-direction:column;line-height:1.15}
.wfp-offline .wfp-status,.wfp-offline .wfp-name{color:var(--wfp-faint)}
.wfp-since{font-size:.6rem;color:var(--wfp-faint)}
.wfp-score,.wfp-rate{font-variant-numeric:tabular-nums;font-size:.92rem;text-align:right;display:flex;flex-direction:column;line-height:1.05;color:var(--wfp-ash)}
.wfp-lbl{font-size:.52rem;text-transform:uppercase;letter-spacing:.1em;color:var(--wfp-faint)}
.wfp-trend{text-align:center;font-size:.7rem}.wfp-t-up{color:var(--wfp-jade)}.wfp-t-down{color:var(--wfp-blood)}.wfp-t-flat{color:var(--wfp-faint)}
.wfp-kinds{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.wfp-kind{font-size:.58rem;color:var(--wfp-mut);background:var(--wfp-panel);border:1px solid var(--wfp-line);border-radius:3px;padding:1px 5px;white-space:nowrap}
.wfp-empty{padding:20px 14px;color:var(--wfp-mut);font-size:.82rem;font-style:italic}
.wfp-foot{padding:8px 14px;border-top:1px solid var(--wfp-line);font-size:.6rem;color:var(--wfp-faint)}
@media (max-width:720px){.wfp-row{grid-template-columns:14px 1fr auto auto}.wfp-rate,.wfp-trend,.wfp-kinds{display:none}}
`;

export function mountWorkforcePanel(el, options = {}) {
  const endpoint = options.endpoint ?? '/api/workforce';
  const pollMs = Math.max(5000, options.pollMs ?? 20_000);
  const url = options.windowDays ? `${endpoint}?windowDays=${encodeURIComponent(String(options.windowDays))}` : endpoint;
  const doFetch = options.fetchImpl ?? (globalThis.fetch ? globalThis.fetch.bind(globalThis) : undefined);
  let stopped = false, timer = null;
  if (typeof document !== 'undefined' && !document.getElementById('wfp-style')) {
    const style = document.createElement('style'); style.id = 'wfp-style'; style.textContent = WORKFORCE_PANEL_CSS;
    document.head.appendChild(style);
  }
  el.innerHTML = renderWorkforcePanelHTML(null, { title: options.title });
  const tick = async () => {
    if (stopped) return;
    try {
      if (!doFetch) throw new Error('fetch unavailable');
      const res = await doFetch(url, { credentials: 'include', headers: { accept: 'application/json' } });
      const j = await res.json().catch(() => null);
      if (!res.ok || !j?.ok) throw new Error(j?.message || j?.error || `HTTP ${res.status}`);
      if (!stopped) el.innerHTML = renderWorkforcePanelHTML(j.data, { title: options.title });
    } catch (e) {
      if (!stopped) el.innerHTML = renderWorkforcePanelHTML(null, { title: options.title, error: e?.message || 'unavailable' });
    } finally {
      if (!stopped) timer = setTimeout(() => void tick(), pollMs);
    }
  };
  void tick();
  return () => { stopped = true; if (timer) clearTimeout(timer); };
}
