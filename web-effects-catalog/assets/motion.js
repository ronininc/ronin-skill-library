/* motion — the house scroll-animation method: stagger, parallax, count-up.
   Hand-coded replacement for the scroll-reveal/timeline/parallax/counter jobs people reach for GSAP to do
   (GSAP's "Standard no-charge" license is not MIT/Apache, so it is not vendored here). Pairs with reveal.js.

   Content is visible by default; every atom is an enhancement that only runs when JS + IntersectionObserver
   are present and prefers-reduced-motion is not set. Nothing here fakes data: a count-up shows the real
   number already written in the HTML, and animates to it.

     Stagger   <ul data-reveal-stagger="80"> <li class="reveal">…</li> … </ul>
               (each .reveal child gets 0, 80, 160 … ms of delay; works with reveal.js)
     Parallax  <img data-parallax="0.15" …>   (speed −1…1; translateY while on screen; static otherwise)
     Count-up  <span data-count-to="1250" data-count-ms="1200">1,250</span>
               (the final value is already in the text; it counts up from 0 once it scrolls in)

   window.RoninMotion.refresh() re-scans after content is added.
*/
(function () {
  var RM = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  var canObserve = 'IntersectionObserver' in window;
  var motionOK = function () { return !RM.matches && canObserve; };

  function stagger() {
    var groups = document.querySelectorAll('[data-reveal-stagger]');
    Array.prototype.forEach.call(groups, function (g) {
      var step = Math.max(0, Math.min(400, parseInt(g.getAttribute('data-reveal-stagger'), 10) || 80));
      var kids = g.querySelectorAll('.reveal');
      Array.prototype.forEach.call(kids, function (el, i) {
        // An explicit data-reveal-delay wins; reduced motion gets no delay at all.
        if (!el.hasAttribute('data-reveal-delay') && motionOK()) el.style.transitionDelay = (i * step) + 'ms';
      });
    });
  }

  var layers = [], ticking = false, onScreen = new Set(), pio = null;
  function paint() {
    ticking = false;
    var vh = window.innerHeight || 1;
    onScreen.forEach(function (el) {
      var r = el.getBoundingClientRect();
      var speed = Math.max(-1, Math.min(1, parseFloat(el.getAttribute('data-parallax')) || 0));
      // Offset is 0 when the element is centred in the viewport, so the resting layout is the authored one.
      var centre = r.top + r.height / 2 - vh / 2;
      el.style.transform = 'translate3d(0,' + (-centre * speed).toFixed(1) + 'px,0)';
    });
  }
  function onScroll() { if (!ticking) { ticking = true; window.requestAnimationFrame(paint); } }
  function parallax() {
    layers = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
    if (!layers.length || !motionOK()) { layers.forEach(function (el) { el.style.transform = ''; }); return; }
    if (pio) pio.disconnect();
    pio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) onScreen.add(e.target); else onScreen.delete(e.target); });
      onScroll();
    }, { rootMargin: '10% 0px' });
    layers.forEach(function (el) { el.style.willChange = 'transform'; pio.observe(el); });
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
  }

  function format(n, el) {
    var lang = el.getAttribute('lang') || document.documentElement.lang || undefined;
    try { return new Intl.NumberFormat(lang).format(n); } catch (e) { return String(n); }
  }
  function countUp() {
    var els = Array.prototype.slice.call(document.querySelectorAll('[data-count-to]:not([data-count-done])'));
    if (!els.length || !motionOK()) return; // the real final value is already in the text
    var cio = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        obs.unobserve(e.target);
        var el = e.target, to = parseFloat(el.getAttribute('data-count-to'));
        if (!isFinite(to)) return;
        var ms = Math.max(200, Math.min(4000, parseInt(el.getAttribute('data-count-ms'), 10) || 1200));
        var finalText = el.textContent, start = null;
        el.setAttribute('data-count-done', '');
        el.setAttribute('aria-label', finalText); // screen readers hear the real value, not the ticking digits
        function frame(t) {
          if (start === null) start = t;
          var p = Math.min(1, (t - start) / ms), eased = 1 - Math.pow(1 - p, 3);
          el.textContent = p < 1 ? format(Math.round(to * eased), el) : finalText;
          if (p < 1) window.requestAnimationFrame(frame);
        }
        window.requestAnimationFrame(frame);
      });
    }, { threshold: 0.6 });
    els.forEach(function (el) { cio.observe(el); });
  }

  function refresh() { stagger(); parallax(); countUp(); }
  window.RoninMotion = { refresh: refresh };
  if (RM.addEventListener) RM.addEventListener('change', function () { if (RM.matches) layers.forEach(function (el) { el.style.transform = ''; }); });
  if (document.readyState !== 'loading') refresh();
  else document.addEventListener('DOMContentLoaded', refresh);
})();
