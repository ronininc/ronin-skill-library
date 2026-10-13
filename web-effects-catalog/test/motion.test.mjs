import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { selectMotion } from '../assets/motion-select.mjs';
const require = createRequire(import.meta.url);
const smooth = require('../assets/smooth-scroll.js');

test('orchestrator: a long marketing page gets reveals, counters, parallax and optional smooth scroll', () => {
  const r = selectMotion({ site_type: 'marketing', content: { viewports: 4, stats: 3, layered_hero: true, lists: 2 } });
  assert.deepEqual(r.methods.sort(), ['lenis-smooth-scroll', 'scroll-animation']);
  assert.deepEqual(r.atoms.sort(), ['motion.js', 'reveal.css', 'reveal.js', 'smooth-scroll.js']);
});
test('orchestrator: app/admin dashboards never get smooth scroll or parallax', () => {
  for (const site_type of ['app', 'admin', 'dashboard']) {
    const r = selectMotion({ site_type, content: { viewports: 5, stats: 4, layered_hero: true } });
    assert.ok(!r.methods.includes('lenis-smooth-scroll'), site_type);
    assert.ok(!r.atoms.includes('smooth-scroll.js'));
    assert.ok(r.reasons.some((x) => x.includes('no smooth scroll')));
  }
});
test('orchestrator: reduced motion or a no-motion brand gets nothing; a one-screen page gets nothing', () => {
  assert.deepEqual(selectMotion({ content: { viewports: 6, stats: 2 }, reduced_motion: true }).methods, []);
  assert.deepEqual(selectMotion({ content: { viewports: 6 }, brand_tokens: { motion: 'none' } }).methods, []);
  assert.deepEqual(selectMotion({ content: { viewports: 1 } }).methods, []);
});
test('smooth scroll: native scrolling unless every condition holds', () => {
  const ok = { reducedMotion: false, siteType: 'marketing', Lenis: function () {}, scrollHeight: 3000, viewportHeight: 800 };
  assert.equal(smooth.decide(ok), null);
  assert.equal(smooth.decide({ ...ok, reducedMotion: true }), 'reduced-motion');
  assert.equal(smooth.decide({ ...ok, siteType: 'admin' }), 'app-or-admin');
  assert.equal(smooth.decide({ ...ok, scrollHeight: 820 }), 'fits-one-viewport');
  assert.equal(smooth.decide({ ...ok, Lenis: undefined }), 'lenis-not-vendored');
});
test('registry: every method has the full schema, a source reference and a checked license', () => {
  const reg = JSON.parse(readFileSync(new URL('../references/motion-methods.json', import.meta.url)));
  const keys = ['name', 'description', 'triggers', 'inputs', 'outputs', 'cost', 'source_reference', 'license', 'status'];
  assert.equal(reg.methods.length, 4);
  for (const m of reg.methods) for (const k of keys) assert.ok(m[k] !== undefined && m[k] !== '', `${m.name}.${k}`);
  const byName = Object.fromEntries(reg.methods.map((m) => [m.name, m]));
  assert.equal(byName['lenis-smooth-scroll'].license.spdx, 'MIT');
  assert.equal(byName['react-bits-components'].status, 'blocked-license');
  assert.match(byName['scroll-animation'].license.note, /GSAP/);
});
