// ===== Full-Stack Qo'llanma — interaktiv imkoniyatlar =====
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };

  // 1. Kunduzgi / tungi rejim
  const themeBtn = $('#themeBtn');
  themeBtn && themeBtn.addEventListener('click', () => {
    const root = document.documentElement;
    const isDark = root.dataset.theme
      ? root.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = isDark ? 'light' : 'dark';
    try { localStorage.setItem('theme', root.dataset.theme); } catch (e) {}
  });

  // 2. Mobil menyu
  const toggleNav = (open) => document.body.classList.toggle('nav-open', open);
  $('#menuBtn') && $('#menuBtn').addEventListener('click', () => toggleNav());
  $('#overlay') && $('#overlay').addEventListener('click', () => toggleNav(false));

  // 3. Kodni nusxalash
  $$('.copy').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const code = btn.closest('.code').querySelector('code').innerText;
      try {
        await navigator.clipboard.writeText(code);
        btn.textContent = 'Nusxalandi ✓';
        btn.classList.add('ok');
      } catch (e) {
        btn.textContent = 'Xatolik';
      }
      setTimeout(() => { btn.textContent = 'Nusxa olish'; btn.classList.remove('ok'); }, 1600);
    });
  });

  // 4. Sintaksisni yoritish (highlight.js mavjud bo'lsa)
  if (window.hljs) {
    $$('.code code').forEach((el) => {
      el.className = el.className.replace('language-jsx', 'language-javascript').replace('language-js', 'language-javascript');
      try { hljs.highlightElement(el); } catch (e) {}
    });
  }

  // 5. O'qish progress chizig'i
  const bar = $('#progress');
  const onScroll = () => {
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    if (bar) bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
  };
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // 6. Mundarijada joriy bo'limni belgilash
  const tocLinks = $$('.toc a');
  if (tocLinks.length && 'IntersectionObserver' in window) {
    const map = new Map(tocLinks.map((a) => [a.getAttribute('href').slice(1), a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          tocLinks.forEach((a) => a.classList.remove('active'));
          const a = map.get(e.target.id);
          a && a.classList.add('active');
        }
      });
    }, { rootMargin: '-70px 0px -70% 0px' });
    $$('.lesson h2[id]').forEach((h) => io.observe(h));
  }

  // 7. Darslarni qidirish (yon menyu va bosh sahifa kartalari)
  const search = $('#search');
  search && search.addEventListener('input', () => {
    const q = search.value.trim().toLowerCase();
    $$('#lessonList li').forEach((li) => li.classList.toggle('hidden', q && !li.textContent.toLowerCase().includes(q)));
    $$('.cards .card').forEach((c) => { c.style.display = q && !c.textContent.toLowerCase().includes(q) ? 'none' : ''; });
    if (q) toggleNav(true);
  });

  // 8. O'qilgan darslarni belgilash
  const done = store.get('doneLessons', []);
  const slugOf = (href) => (href.match(/darslar\/([\w-]+)\.html/) || [])[1];
  const markDone = () => {
    $$('#lessonList a').forEach((a) => a.classList.toggle('done', done.includes(slugOf(a.href)) && !a.classList.contains('active')));
    $$('.cards .card').forEach((c) => c.classList.toggle('done', done.includes(slugOf(c.href))));
    const counter = $('#doneCount');
    if (counter) counter.textContent = done.length;
  };
  const current = slugOf(location.pathname);
  const lesson = $('.lesson');
  if (lesson && current) {
    const btn = document.createElement('button');
    btn.className = 'done-btn';
    const paint = () => { btn.textContent = done.includes(current) ? '✓ Dars o\'qilgan deb belgilangan' : '☐ Darsni o\'qib bo\'ldim'; };
    paint();
    btn.addEventListener('click', () => {
      const i = done.indexOf(current);
      i === -1 ? done.push(current) : done.splice(i, 1);
      store.set('doneLessons', done);
      paint(); markDone();
    });
    const pager = $('.pager', lesson);
    lesson.insertBefore(btn, pager);
  }
  markDone();

  // Joriy darsni yon menyuda ko'rinadigan qilish
  const active = $('#lessonList a.active');
  const side = $('#sidebar');
  if (active && side) side.scrollTop = active.offsetTop - side.clientHeight / 2;
})();
