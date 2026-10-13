/* smooth-scroll — opt-in Lenis smooth scrolling for marketing/content sites that run past one viewport.
   Lenis (github.com/darkroomengineering/lenis) is MIT. This wrapper never fetches it: vendor the exact
   dist file into /assets/ yourself (pinned version, recorded in the site README) so window.Lenis exists.

   Native scrolling stays the default. init() returns null (and leaves native scroll alone) when:
     - prefers-reduced-motion is set
     - the site is an app/admin/dashboard/tool (smooth scroll fights in-app scroll areas and keyboard use)
     - the page is not longer than about one viewport
     - Lenis is not vendored on the page
       <script src="/assets/lenis.min.js"></script>
       <script src="/assets/smooth-scroll.js"></script>
       <script>RoninSmoothScroll.init({ siteType: 'marketing' });</script>
*/
(function (root) {
  // Opt-in only: smooth scroll runs for site types explicitly named here; anything else (app, admin, unknown) is native.
  var SMOOTH_TYPES = ['marketing', 'content', 'landing', 'editorial', 'portfolio'];
  function decide(o) {
    if (o.reducedMotion) return 'reduced-motion';
    if (SMOOTH_TYPES.indexOf(String(o.siteType || '').toLowerCase()) === -1) return 'not-a-marketing-or-content-site';
    if (!(o.scrollHeight > o.viewportHeight * 1.05)) return 'fits-one-viewport';
    if (typeof o.Lenis !== 'function') return 'lenis-not-vendored';
    return null;
  }
  var api = {
    decide: decide,
    init: function (opts) {
      opts = opts || {};
      var w = root, d = w.document;
      var why = decide({
        reducedMotion: !!(w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches),
        siteType: opts.siteType, Lenis: w.Lenis,
        scrollHeight: d.documentElement.scrollHeight, viewportHeight: w.innerHeight,
      });
      if (why) { api.skipped = why; return null; }
      var lenis = new w.Lenis({ lerp: typeof opts.lerp === 'number' ? opts.lerp : 0.1, smoothWheel: opts.smoothWheel !== false });
      var running = true;
      function raf(t) { if (!running) return; lenis.raf(t); w.requestAnimationFrame(raf); }
      w.requestAnimationFrame(raf);
      api.instance = lenis;
      api.destroy = function () { running = false; if (lenis.destroy) lenis.destroy(); api.instance = null; };
      // Reduced motion turned on later: back to native scrolling immediately.
      var rm = w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)');
      if (rm && rm.addEventListener) rm.addEventListener('change', function () { if (rm.matches) api.destroy(); });
      return lenis;
    },
  };
  root.RoninSmoothScroll = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
