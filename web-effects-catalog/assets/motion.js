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
      var raw = parseInt(g.getAttribute('data-reveal-stagger'), 10);
      var step = Math.max(0, Math.min(400, isNaN(raw) ? 80 : raw)); // 0 is a valid choice
      var kids = g.querySelectorAll('.reveal');
      Array.prototype.forEach.call(kids, function (el, i) {
        // An explicit data-reveal-delay wins; reduced motion gets no delay at all.
        if (!el.hasAttribute('data-reveal-delay') && motionOK()) el.style.transitionDelay = (i * step) + 'ms';
      });
    });
  }

  var layers = [], ticking = false, onScreen = new Set(), pio = null, listening = false;
  function offsetOf(el) { return parseFloat(el.getAttribute('data-parallax-y')) || 0; }
  function paint() {
    ticking = false;
    if (!motionOK()) return;
    var vh = window.innerHeight || 1;
    onScreen.forEach(function (el) {
      if (!el.isConnected) { onScreen.delete(el); return; }
      var r = el.getBoundingClientRect();
      var speed = Math.max(-1, Math.min(1, parseFloat(el.getAttribute('data-parallax')) || 0));
      // Measure the UNtransformed position (rect minus the offset we applied), so the offset never feeds back.
      var centre = (r.top - offsetOf(el)) + r.height / 2 - vh / 2;
      var y = Math.round(-centre * speed * 10) / 10;
      el.setAttribute('data-parallax-y', String(y));
      el.style.transform = 'translate3d(0,' + y + 'px,0)';
    });
  }
  function onScroll() { if (!ticking) { ticking = true; window.requestAnimationFrame(paint); } }
  function stopParallax() {
    if (pio) { pio.disconnect(); pio = null; }
    onScreen.clear();
    layers.forEach(function (el) { el.style.transform = ''; el.style.willChange = ''; el.removeAttribute('data-parallax-y'); });
  }
  function parallax() {
    stopParallax();
    layers = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
    if (!layers.length || !motionOK()) return;
    pio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) onScreen.add(e.target); else onScreen.delete(e.target); });
      onScroll();
    }, { rootMargin: '10% 0px' });
    layers.forEach(function (el) { el.style.willChange = 'transform'; pio.observe(el); });
    if (!listening) { // once per page, however often refresh() runs
      listening = true;
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll, { passive: true });
    }
  }

  function decimalsOf(s) { var m = String(s).match(/\.(\d+)/); return m ? m[1].length : 0; }
  function format(n, el, decimals) {
    var lang = el.getAttribute('lang') || document.documentElement.lang || undefined;
    try { return new Intl.NumberFormat(lang, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n); } catch (e) { return n.toFixed(decimals); }
  }
  var counting = [];
  function countUp() {
    var els = Array.prototype.slice.call(document.querySelectorAll('[data-count-to]:not([data-count-done])'));
    if (!els.length || !motionOK()) return; // the real final value is already in the text
    var cio = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        obs.unobserve(e.target);
        var el = e.target, raw = el.getAttribute('data-count-to'), to = parseFloat(raw);
        if (!isFinite(to)) return;
        var ms = Math.max(200, Math.min(4000, parseInt(el.getAttribute('data-count-ms'), 10) || 1200));
        var finalText = el.textContent, start = null, decimals = decimalsOf(raw);
        el.setAttribute('data-count-done', '');
        // Screen readers get the real value from a visually hidden copy; the ticking digits are hidden from them.
        var live = document.createElement('span');
        live.textContent = finalText;
        live.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap';
        var tick = document.createElement('span');
        tick.setAttribute('aria-hidden', 'true');
        el.textContent = ''; el.appendChild(tick); el.appendChild(live);
        var job = { done: false };
        counting.push(job);
        function finish() { job.done = true; el.textContent = finalText; }
        function frame(t) {
          if (job.done) return;
          if (!motionOK()) { finish(); return; }
          if (start === null) start = t;
          var p = Math.min(1, (t - start) / ms), eased = 1 - Math.pow(1 - p, 3);
          if (p < 1) { tick.textContent = format(to * eased, el, decimals); window.requestAnimationFrame(frame); } else finish();
        }
        job.finish = finish;
        window.requestAnimationFrame(frame);
      });
    }, { threshold: 0.6 });
    els.forEach(function (el) { cio.observe(el); });
  }

  function refresh() { stagger(); parallax(); countUp(); }
  window.RoninMotion = { refresh: refresh };
  // Turning reduced motion on mid-visit stops everything now: parallax is removed, counters jump to their value.
  if (RM.addEventListener) RM.addEventListener('change', function () {
    if (!RM.matches) return;
    stopParallax();
    counting.forEach(function (job) { if (!job.done && job.finish) job.finish(); });
  });
  if (document.readyState !== 'loading') refresh();
  else document.addEventListener('DOMContentLoaded', refresh);
})();
