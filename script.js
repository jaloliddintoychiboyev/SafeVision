(function () {
  'use strict';

  /* ---------- Language toggle (EN / UZ) ---------- */
  var STORE_KEY = 'safevision-lang';
  var toggle = document.getElementById('langToggle');
  var i18nNodes = document.querySelectorAll('[data-en],[data-uz]');

  function applyLang(lang) {
    document.documentElement.lang = lang;
    i18nNodes.forEach(function (node) {
      var val = node.getAttribute('data-' + lang);
      if (val !== null) node.textContent = val;
    });
    if (toggle) {
      toggle.querySelectorAll('span[data-lang]').forEach(function (s) {
        s.classList.toggle('is-active', s.getAttribute('data-lang') === lang);
      });
    }
    try { localStorage.setItem(STORE_KEY, lang); } catch (e) {}
  }

  var saved = 'en';
  try { saved = localStorage.getItem(STORE_KEY) || 'en'; } catch (e) {}
  applyLang(saved);

  if (toggle) {
    toggle.addEventListener('click', function () {
      var current = document.documentElement.lang === 'uz' ? 'uz' : 'en';
      applyLang(current === 'en' ? 'uz' : 'en');
    });
  }

  /* ---------- Nav shadow on scroll ---------- */
  var nav = document.getElementById('nav');
  function onScroll() {
    if (nav) nav.classList.toggle('is-scrolled', window.scrollY > 10);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- Reveal on scroll ---------- */
  var reveals = document.querySelectorAll(
    '.section .card, .section .stat, .step, .tl, .highlight, .specs, .table-wrap, .callout, .alloc, .budget__stat, .section__title'
  );
  reveals.forEach(function (el) { el.classList.add('reveal'); });

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add('is-visible'); });
  }

  /* ---------- Count-up for numeric stats ---------- */
  var counters = document.querySelectorAll('[data-count]');
  function format(n) { return n.toLocaleString('en-US').replace(/,/g, ' '); }

  function animateCount(el) {
    var target = parseInt(el.getAttribute('data-count'), 10);
    if (isNaN(target)) return;
    var dur = 1400, start = null;
    function tick(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = format(Math.floor(eased * target));
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = format(target);
    }
    requestAnimationFrame(tick);
  }

  if ('IntersectionObserver' in window) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          co.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { co.observe(el); });
  }
})();
