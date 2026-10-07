/* Taqdimot boshqaruvi: klaviatura, sichqoncha, surish, to'liq ekran, izohlar, testlar */
(function () {
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var cur = 0;
  var barFill = document.getElementById('barFill');
  var counter = document.getElementById('counter');
  var notesText = document.getElementById('notesText');

  // Slaydni ekranga moslash (1280x720 -> oyna o'lchami)
  function fit() {
    var k = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    document.documentElement.style.setProperty('--k', k);
  }

  // Matn sig'masa — shrift o'lchamini kichraytirish
  function shrink(slide) {
    var body = slide.querySelector('.s-body');
    if (!body || body.dataset.fitted) return;
    var size = 28;
    body.style.fontSize = size + 'px';
    var tooBig = function () {
      return slide.scrollHeight > slide.clientHeight + 1 ||
        Array.prototype.some.call(body.querySelectorAll('.col'), function (c) { return c.scrollHeight > c.clientHeight + 1; }) ||
        Array.prototype.some.call(body.querySelectorAll('pre, pre code'), function (p) { return p.scrollWidth > p.clientWidth + 1; });
    };
    while (tooBig() && size > 14) {
      size -= 1;
      body.style.fontSize = size + 'px';
    }
    body.dataset.fitted = '1';
  }

  function show(n) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    slides[cur].classList.remove('active');
    cur = n;
    var s = slides[cur];
    s.classList.add('active');
    shrink(s);
    counter.textContent = (cur + 1) + ' / ' + slides.length;
    barFill.style.width = ((cur + 1) / slides.length * 100) + '%';
    notesText.textContent = s.dataset.notes || '—';
    if (location.hash !== '#' + (cur + 1)) history.replaceState(null, '', '#' + (cur + 1));
  }
  function next() { if (cur < slides.length - 1) show(cur + 1); else if (window.DECK_NAV.next) location.href = window.DECK_NAV.next; }
  function prev() { if (cur > 0) show(cur - 1); }

  function fullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
  }

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key;
    if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'Enter') { e.preventDefault(); next(); }
    else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Backspace') { e.preventDefault(); prev(); }
    else if (k === 'Home') show(0);
    else if (k === 'End') show(slides.length - 1);
    else if (k === 'f' || k === 'F') fullscreen();
    else if (k === 'n' || k === 'N') document.body.classList.toggle('notes-on');
    else if (k === 'Escape') document.body.classList.remove('notes-on');
  });

  document.getElementById('nextBtn').onclick = next;
  document.getElementById('prevBtn').onclick = prev;
  document.getElementById('fsBtn').onclick = fullscreen;
  document.getElementById('notesBtn').onclick = function () { document.body.classList.toggle('notes-on'); };

  // Slaydning chap/o'ng tomonini bosish
  document.getElementById('deck').addEventListener('click', function (e) {
    if (e.target.closest('button, a, pre, .s-table')) return;
    if (window.getSelection && String(window.getSelection())) return;
    if (e.clientX < window.innerWidth * 0.3) prev(); else next();
  });

  // Telefonda surish
  var sx = null;
  document.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
  document.addEventListener('touchend', function (e) {
    if (sx === null) return;
    var dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 50) { if (dx < 0) next(); else prev(); }
    sx = null;
  });

  // Testlar: variantni bosganda to'g'ri javobni ko'rsatish
  document.querySelectorAll('.quiz-opts').forEach(function (box) {
    var opts = box.querySelectorAll('.opt');
    var longest = 0;
    opts.forEach(function (o) { longest = Math.max(longest, o.textContent.length); });
    if (longest > 48 || opts.length !== 4) box.classList.add('long');
    opts.forEach(function (o) {
      o.addEventListener('click', function () {
        if (o.dataset.ok === '1') o.classList.add('right');
        else {
          o.classList.add('wrong');
          opts.forEach(function (x) { if (x.dataset.ok === '1') x.classList.add('right'); });
        }
      });
    });
  });

  // Kodni yoritish
  if (window.hljs) document.querySelectorAll('.s-code pre code').forEach(function (el) { try { hljs.highlightElement(el); } catch (e) {} });

  // Sichqoncha qimirlaganda boshqaruv panelini ko'rsatish
  var t;
  document.addEventListener('mousemove', function () {
    document.body.classList.add('show-ui');
    clearTimeout(t);
    t = setTimeout(function () { document.body.classList.remove('show-ui'); }, 1800);
  });

  window.addEventListener('resize', fit);
  window.addEventListener('beforeprint', function () { slides.forEach(shrink); });
  fit();
  var start = parseInt((location.hash || '').slice(1), 10);
  slides[0].classList.add('active');
  show(isNaN(start) ? 0 : start - 1);
})();
