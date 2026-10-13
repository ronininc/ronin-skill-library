// The website-build orchestrator's motion step. Run AFTER the design direction is chosen (website-build-standard):
// it picks only the motion that fits the site, never motion for its own sake. Pure, so it is testable and cheap;
// the heavy part of a build is the build, not this choice.
//   selectMotion({ site_type, content: { viewports, stats, layered_hero, lists }, brand_tokens, reduced_motion })
//   → { methods: [...method names], atoms: [...asset files], reasons: [...] }
const APP_TYPES = new Set(['app', 'admin', 'dashboard', 'tool', 'portal']);

export function selectMotion({ site_type = 'marketing', content = {}, brand_tokens = {}, reduced_motion = false } = {}) {
  const reasons = [];
  const methods = new Set(), atoms = new Set();
  const app = APP_TYPES.has(String(site_type).toLowerCase());
  if (reduced_motion) {
    reasons.push('prefers-reduced-motion: no motion methods; content renders static');
    return { methods: [], atoms: [], reasons };
  }
  if (app) reasons.push(`${site_type}: no smooth scroll and no parallax; only quiet entrance reveals for content cards`);
  const viewports = Number(content.viewports) || 1;
  if (viewports > 1) {
    methods.add('scroll-animation'); atoms.add('reveal.js'); atoms.add('reveal.css');
    reasons.push('content runs past one viewport: scroll-entrance reveals');
    if ((Number(content.lists) || 0) > 0) { atoms.add('motion.js'); reasons.push('lists/grids: stagger their reveals'); }
  }
  if (!app && (Number(content.stats) || 0) > 0) { methods.add('scroll-animation'); atoms.add('motion.js'); reasons.push('real numbers on the page: count-up to the authored value'); }
  if (!app && content.layered_hero) { methods.add('scroll-animation'); atoms.add('motion.js'); reasons.push('layered hero: gentle parallax'); }
  if (!app && viewports > 2) {
    methods.add('lenis-smooth-scroll'); atoms.add('smooth-scroll.js');
    reasons.push('long marketing/content page: optional Lenis smooth scroll (needs Lenis vendored; native scroll otherwise)');
  }
  if (brand_tokens && brand_tokens.motion === 'none') {
    reasons.push('brand tokens ask for no motion: honoured');
    return { methods: [], atoms: [], reasons };
  }
  return { methods: [...methods], atoms: [...atoms], reasons };
}
