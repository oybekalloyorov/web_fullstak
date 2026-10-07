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
      el.className = el.className.replace(/\blanguage-jsx?\b/, 'language-javascript');
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
  const done = store.get('doneLessons2', []);
  // Dars kaliti: 'darslar/01-...', '8-sinf/05-...' yoki 'cs/03-...'
  const slugOf = (href) => (href.match(/((?:darslar|8-sinf|cs)\/\d[\w-]*)\.html/) || [])[1];
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
      store.set('doneLessons2', done);
      paint(); markDone();
    });
    const pager = $('.pager', lesson);
    lesson.insertBefore(btn, pager);
  }
  markDone();


  // 9. "Sinab ko'rish" — HTML/CSS/JS kodini brauzerning o'zida tahrirlash va ishga tushirish
  $$('.code[data-play] .run').forEach((btn) => {
    btn.addEventListener('click', () => {
      const block = btn.closest('.code');
      let pg = block.nextElementSibling;
      if (pg && pg.classList.contains('playground')) { pg.remove(); btn.textContent = '▶ Sinab ko\'rish'; return; }
      const source = block.querySelector('code').innerText;
      pg = document.createElement('div');
      pg.className = 'playground';
      pg.innerHTML = '<div class="pg-head"><span>✏️ Kodni o\'zgartiring — natija o\'ng tomonda darhol yangilanadi</span>' +
        '<span><button type="button" data-act="reset">↺ Asl holiga</button> <button type="button" data-act="open">⧉ Yangi oynada</button></span></div>' +
        '<div class="pg-body"><textarea spellcheck="false" aria-label="Kod muharriri"></textarea><iframe title="Natija" sandbox="allow-scripts allow-modals allow-forms allow-same-origin"></iframe></div>';
      const ta = pg.querySelector('textarea');
      const frame = pg.querySelector('iframe');
      ta.value = source;
      const lang = (block.querySelector('code').className.match(/language-(\w+)/) || [])[1];
      const wrap = (code) => {
        if (lang === 'css') return '<!doctype html><meta charset="utf-8"><style>' + code + '</style><body><h1>Sarlavha</h1><p>Paragraf matni</p><button>Tugma</button></body>';
        if (lang === 'javascript' || lang === 'js') return '<!doctype html><meta charset="utf-8"><body style="font-family:system-ui"><pre id="out"></pre><script>' +
          'const __o=document.getElementById("out");const __log=console.log;console.log=(...a)=>{__o.textContent+=a.map(x=>typeof x==="object"?JSON.stringify(x):String(x)).join(" ")+"\\n";__log(...a)};' +
          'window.onerror=(m)=>{__o.textContent+="❌ Xato: "+m+"\\n"};<\/script><script>' + code + '<\/script></body>';
        return code.includes('<html') || code.includes('<!DOCTYPE') || code.includes('<!doctype') ? code : '<!doctype html><meta charset="utf-8">' + code;
      };
      let t;
      const render = () => { frame.srcdoc = wrap(ta.value); };
      ta.addEventListener('input', () => { clearTimeout(t); t = setTimeout(render, 350); });
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const s = ta.selectionStart;
          ta.setRangeText('  ', s, ta.selectionEnd, 'end');
        }
      });
      pg.addEventListener('click', (e) => {
        const act = e.target.dataset.act;
        if (act === 'reset') { ta.value = source; render(); }
        if (act === 'open') {
          const url = URL.createObjectURL(new Blob([wrap(ta.value)], { type: 'text/html' }));
          window.open(url, '_blank', 'noopener');
        }
      });
      block.after(pg);
      btn.textContent = '✕ Yopish';
      render();
    });
  });

  // 10. Interaktiv test savollari: <div class="quiz" data-answer="2"> (1 dan boshlab)
  const quizzes = $$('.quiz');
  if (quizzes.length) {
    let right = 0, answered = 0;
    let score = null;
    if (quizzes.length >= 3) {
      score = document.createElement('div');
      score.className = 'quiz-score';
      score.hidden = true;
      quizzes[quizzes.length - 1].after(score);
    }
    quizzes.forEach((q) => {
      const correct = Number(q.dataset.answer);
      const items = $$('li', q);
      items.forEach((li, i) => {
        li.tabIndex = 0;
        const choose = () => {
          if (q.classList.contains('answered')) return;
          q.classList.add('answered');
          answered++;
          if (i + 1 === correct) right++; else li.classList.add('wrong');
          items[correct - 1] && items[correct - 1].classList.add('right');
          if (score) {
            score.hidden = false;
            score.textContent = `Natija: ${right} / ${answered} to'g'ri` +
              (answered === quizzes.length ? ` — ${right === quizzes.length ? 'A\'lo! 🏆' : right >= quizzes.length * 0.7 ? 'Yaxshi! 👍' : 'Mavzuni yana bir bor takrorlang 📖'}` : ` (jami ${quizzes.length} ta savol)`);
          }
        };
        li.addEventListener('click', choose);
        li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } });
      });
    });
  }

  // Joriy darsni yon menyuda ko'rinadigan qilish
  const active = $('#lessonList a.active');
  const side = $('#sidebar');
  if (active && side) side.scrollTop = active.offsetTop - side.clientHeight / 2;
})();
