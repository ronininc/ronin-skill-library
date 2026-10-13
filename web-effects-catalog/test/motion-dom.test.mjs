// motion.js against a minimal fake DOM: an observer that reports every element visible, animation frames the test
// drives, and getBoundingClientRect that INCLUDES the applied transform (as browsers do), to catch feedback loops.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const SRC = readFileSync(new URL('../assets/motion.js', import.meta.url), 'utf8');

function world({ reduced = false } = {}) {
  const listeners = [], frames = [], rmHandlers = [];
  let scrollY = 0;
  const mk = (attrs, layoutTop = 0, text = '') => {
    const el = {
      attrs: { ...attrs }, style: {}, textContent: text, children: [], isConnected: true, classList: { contains: () => false, add() {} },
      getAttribute: (k) => (k in el.attrs ? el.attrs[k] : null), setAttribute: (k, v) => { el.attrs[k] = String(v); },
      hasAttribute: (k) => k in el.attrs, removeAttribute: (k) => { delete el.attrs[k]; },
      appendChild: (c) => { el.children.push(c); return c; },
      querySelector: (sel) => el.children.find((c) => (sel.includes('aria-hidden') ? c.attrs['aria-hidden'] === 'true' : !c.attrs['aria-hidden'])) ?? null,
      querySelectorAll: () => [],
      getBoundingClientRect: () => {
        const m = /translate3d\(0,\s*(-?[\d.]+)px/.exec(el.style.transform || '');
        const top = layoutTop - scrollY + (m ? parseFloat(m[1]) : 0);
        return { top, bottom: top + 200, height: 200 };
      },
    };
    Object.defineProperty(el, 'textContent', { get() { return el.children.length ? el.children.map((x) => x.textContent).join('') : el._t; }, set(v) { el._t = v; el.children = []; } });
    el._t = text;
    return el;
  };
  const layer = mk({ 'data-parallax': '-1' }, 1200);
  const count = mk({ 'data-count-to': '4.9' }, 600, '4.9');
  const all = { '[data-parallax]': [layer], '[data-count-to]:not([data-count-done])': [count], '[data-reveal-stagger]': [] };
  const document = {
    readyState: 'complete', documentElement: { lang: 'en' },
    querySelectorAll: (sel) => (sel === '[data-count-to]:not([data-count-done])' ? all[sel].filter((e) => !e.hasAttribute('data-count-done')) : all[sel] ?? []),
    createElement: () => mk({}),
    addEventListener() {},
  };
  const rm = { matches: reduced, addEventListener: (_, fn) => rmHandlers.push(fn) };
  const window = {
    innerHeight: 800, matchMedia: () => rm,
    addEventListener: (type, fn) => listeners.push({ type, fn }),
    requestAnimationFrame: (fn) => frames.push(fn),
  };
  window.IntersectionObserver = class { constructor(cb) { this.cb = cb; } observe(el) { this.cb([{ isIntersecting: true, target: el }], this); } unobserve() {} disconnect() {} };
  vm.runInNewContext(SRC, { window, document, IntersectionObserver: window.IntersectionObserver, Intl, Math, String, parseFloat, parseInt, isFinite, isNaN, Set, Array });
  const flush = (t = 0) => { const run = frames.splice(0); run.forEach((f) => f(t)); };
  const scroll = (y) => { scrollY = y; listeners.filter((l) => l.type === 'scroll').forEach((l) => l.fn()); flush(); };
  return { window, layer, count, listeners, flush, scroll, rm, rmHandlers };
}

test('refresh() never stacks scroll/resize listeners', () => {
  const w = world();
  const before = w.listeners.length;
  w.window.RoninMotion.refresh(); w.window.RoninMotion.refresh(); w.window.RoninMotion.refresh();
  assert.equal(before, 2);
  assert.equal(w.listeners.length, 2);
});

test('parallax has no feedback: repeated paints at the same scroll give the same offset, even at speed -1', () => {
  const w = world();
  w.scroll(400);
  const a = w.layer.style.transform;
  for (let i = 0; i < 5; i++) w.scroll(400);
  assert.equal(w.layer.style.transform, a, 'stable');
  const y = parseFloat(/(-?[\d.]+)px/.exec(a)[1]);
  assert.ok(Number.isFinite(y) && Math.abs(y) < 2000, `bounded offset ${y}`);
});

test('count-up keeps decimals and gives screen readers the real value', () => {
  const w = world();
  w.flush(0); w.flush(600);
  const tick = w.count.children.find((c) => c.attrs['aria-hidden'] === 'true');
  const live = w.count.children.find((c) => !c.attrs['aria-hidden']);
  assert.match(tick.textContent, /^\d\.\d$/, `mid value ${tick.textContent}`);
  assert.equal(live.textContent, '4.9');
  assert.equal(w.count.hasAttribute('aria-label'), false);
  w.flush(5000);
  assert.equal(w.count.textContent, '4.9');
});

test('reduced motion turned on mid-visit stops parallax and finishes counters', () => {
  const w = world();
  w.scroll(400); w.flush(0);
  w.rm.matches = true; w.rmHandlers.forEach((f) => f());
  assert.equal(w.layer.style.transform, '');
  assert.equal(w.count.textContent, '4.9');
  w.scroll(900);
  assert.equal(w.layer.style.transform, '', 'no repaint after the switch');
});

test('reduced motion from the start: nothing moves, nothing is rewritten', () => {
  const w = world({ reduced: true });
  w.scroll(400); w.flush(0);
  assert.equal(w.layer.style.transform ?? '', '');
  assert.equal(w.count.textContent, '4.9');
  assert.equal(w.count.hasAttribute('data-count-done'), false);
});
