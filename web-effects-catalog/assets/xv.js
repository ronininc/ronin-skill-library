/* xv — exploded-view inspector. Hover/focus/tap a scene; its parts blow apart,
   float as if in a vacuum, then coalesce back. Self-contained, no dependencies.

   Markup:
     <div class="xv-scene" data-xv aria-label="Açaí bowl">
       <div class="xv-stage">
         <div class="xv-part" data-label="Açaí base">…</div>
         <div class="xv-part" data-label="Granola" data-dx="-120" data-dy="-40">…</div>
         …
       </div>
     </div>

   Per-part optional data attrs (px / deg). Omit dx+dy to auto-compute a radial
   burst from the scene centre:
     data-dx data-dy data-dz   explode offset   (auto radial if dx+dy omitted)
     data-dr                   explode rotation (auto small random if omitted)
   Scene optional:
     data-xv-spread            multiply the burst distance (default 1)
*/
(function () {
  var RM = window.matchMedia('(prefers-reduced-motion: reduce)');
  var HOVER = window.matchMedia('(hover: hover)');

  function initAll(root) {
    (root || document).querySelectorAll('[data-xv]').forEach(setup);
  }

  function attr(el, name, def) {
    var v = el.getAttribute(name);
    return v == null ? def : parseFloat(v);
  }

  function setup(scene) {
    if (scene.__xv) return;
    scene.__xv = true;

    var spread = attr(scene, 'data-xv-spread', 1);
    var parts = Array.prototype.slice.call(scene.querySelectorAll('.xv-part'));

    // Split the two motions: outer .xv-part carries the transitioned explode
    // offset; an injected inner wrapper carries the per-frame vacuum drift so
    // the drift never fights the CSS transition.
    parts.forEach(function (p) {
      var inner = p.querySelector(':scope > .xv-inner');
      if (!inner) {
        inner = document.createElement('div');
        inner.className = 'xv-inner';
        while (p.firstChild) inner.appendChild(p.firstChild);
        p.appendChild(inner);
      }
      p.__inner = inner;
      p.__phase = Math.random() * Math.PI * 2;
    });

    function measure() {
      var cb = scene.getBoundingClientRect();
      var cx = cb.left + cb.width / 2, cy = cb.top + cb.height / 2;
      var reach = Math.max(cb.width, cb.height) * 0.34 * spread;
      parts.forEach(function (p) {
        var dxA = p.getAttribute('data-dx'), dyA = p.getAttribute('data-dy');
        var dx, dy;
        if (dxA == null && dyA == null) {
          var b = p.getBoundingClientRect();
          var vx = (b.left + b.width / 2) - cx;
          var vy = (b.top + b.height / 2) - cy;
          var len = Math.hypot(vx, vy) || 1;
          dx = (vx / len) * reach;
          dy = (vy / len) * reach;
        } else {
          dx = (parseFloat(dxA) || 0) * spread;
          dy = (parseFloat(dyA) || 0) * spread;
        }
        var dz = p.getAttribute('data-dz');
        dz = dz != null ? parseFloat(dz) * spread : (40 + Math.random() * 70) * spread;
        var dr = p.getAttribute('data-dr');
        dr = dr != null ? parseFloat(dr) : (Math.random() * 16 - 8);
        p.style.setProperty('--xv-dx', dx.toFixed(1) + 'px');
        p.style.setProperty('--xv-dy', dy.toFixed(1) + 'px');
        p.style.setProperty('--xv-dz', dz.toFixed(1) + 'px');
        p.style.setProperty('--xv-dr', dr.toFixed(1) + 'deg');
      });
    }
    measure();
    window.addEventListener('resize', debounce(measure, 150));

    // Accessibility: the scene is an operable control in every mode.
    if (!scene.hasAttribute('tabindex')) scene.tabIndex = 0;
    scene.setAttribute('role', 'button');
    if (!scene.getAttribute('aria-label')) scene.setAttribute('aria-label', 'Explode to inspect parts');
    scene.setAttribute('aria-pressed', 'false');

    if (RM.matches) return wireStatic(scene);

    var raf = 0, t0 = 0;
    function loop(t) {
      if (!t0) t0 = t;
      var el = (t - t0) / 1000;
      parts.forEach(function (p) {
        var bob = Math.sin(el * 1.35 + p.__phase) * 4;   // gentle vertical drift
        var sway = Math.cos(el * 1.05 + p.__phase) * 3;  // gentle lateral drift
        p.__inner.style.transform = 'translate3d(' + sway.toFixed(2) + 'px,' + bob.toFixed(2) + 'px,0)';
      });
      raf = requestAnimationFrame(loop);
    }
    function explode() {
      scene.classList.add('is-xv');
      scene.setAttribute('aria-pressed', 'true');
      if (!raf) { t0 = 0; raf = requestAnimationFrame(loop); }
    }
    function coalesce() {
      scene.classList.remove('is-xv');
      scene.setAttribute('aria-pressed', 'false');
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      parts.forEach(function (p) { p.__inner.style.transform = ''; });
      resetTilt();
    }
    function toggle() { scene.classList.contains('is-xv') ? coalesce() : explode(); }

    function tilt(e) {
      var b = scene.getBoundingClientRect();
      var px = (e.clientX - b.left) / b.width - 0.5;
      var py = (e.clientY - b.top) / b.height - 0.5;
      scene.style.setProperty('--xv-tx', (py * -9).toFixed(2) + 'deg');
      scene.style.setProperty('--xv-ty', (px * 11).toFixed(2) + 'deg');
    }
    function resetTilt() {
      scene.style.setProperty('--xv-tx', '0deg');
      scene.style.setProperty('--xv-ty', '0deg');
    }

    if (HOVER.matches) {
      scene.addEventListener('pointerenter', explode);
      scene.addEventListener('pointermove', tilt);
      scene.addEventListener('pointerleave', coalesce);
      scene.addEventListener('focus', explode);
      scene.addEventListener('blur', coalesce);
    } else {
      // Touch: no hover — tap pins the exploded state, tap again coalesces.
      scene.addEventListener('click', toggle);
    }
    scene.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
  }

  // Reduced-motion / no-animation path: no travel, no drift — the scene still
  // reveals its part labels on hover/focus/tap so the information is never lost.
  function wireStatic(scene) {
    scene.classList.add('xv-static');
    var on = function () { scene.classList.add('is-xv'); scene.setAttribute('aria-pressed', 'true'); };
    var off = function () { scene.classList.remove('is-xv'); scene.setAttribute('aria-pressed', 'false'); };
    scene.addEventListener('pointerenter', on);
    scene.addEventListener('pointerleave', off);
    scene.addEventListener('focus', on);
    scene.addEventListener('blur', off);
    scene.addEventListener('click', function () { scene.classList.toggle('is-xv'); });
  }

  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  if (document.readyState !== 'loading') initAll();
  else document.addEventListener('DOMContentLoaded', function () { initAll(); });
  window.XV = { init: initAll };
})();
