/* reveal — accessible scroll-entrance animations (the slideInUp family).
   Content is visible by default; motion is an enhancement layered on top only
   when JS + IntersectionObserver are present and motion is allowed.

   Put this ONE line as the first thing in <head> so the start-hidden state is
   armed before first paint (prevents a flash of already-visible content):
     <script>document.documentElement.classList.add('reveal-armed');</script>

   Then mark elements:
     <div class="reveal">…</div>                 (default: slide up + fade)
     <div class="reveal" data-reveal="left">…</div>
     <div class="reveal" data-reveal="zoom" data-reveal-delay="120">…</div>

   Directions: up (default) · down · left · right · zoom · fade
*/
(function () {
  var docEl = document.documentElement;
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)');

  function showAll(els) {
    els.forEach(function (el) { el.classList.add('is-in'); });
  }

  function run() {
    var els = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
    if (!els.length) return;

    // If motion is off, or the browser can't observe, reveal everything now.
    if (RM.matches || !('IntersectionObserver' in window)) {
      docEl.classList.remove('reveal-armed');
      showAll(els);
      return;
    }

    els.forEach(function (el) {
      var d = el.getAttribute('data-reveal-delay');
      if (d) el.style.transitionDelay = parseInt(d, 10) + 'ms';
    });

    var io = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    els.forEach(function (el) { io.observe(el); });

    // Safety net: if anything is still hidden after load (observer missed, etc.),
    // reveal it so content can never get stuck invisible.
    window.addEventListener('load', function () {
      setTimeout(function () {
        els.forEach(function (el) {
          if (!el.classList.contains('is-in') &&
              el.getBoundingClientRect().top < window.innerHeight) {
            el.classList.add('is-in');
          }
        });
      }, 1200);
    });
  }

  if (document.readyState !== 'loading') run();
  else document.addEventListener('DOMContentLoaded', run);
})();
