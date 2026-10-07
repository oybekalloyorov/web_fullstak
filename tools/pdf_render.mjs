// Sayt sahifalaridan PDF yasash (Playwright + Chromium).
// Ishlatish: node tools/pdf_render.mjs jobs.json
//   jobs.json: [{ "html": "8-sinf/01-....html", "pdf": "8-sinf/pdf/01-....pdf", "kind": "lesson" | "deck", "title": "..." },
//               { "htmls": [...], "pdf": "...", "kind": "combined", "title": "..." }]  — butun kurs bitta PDF
// Ixtiyoriy: HLJS_DIR — highlight.js fayllari turgan papka (internet bo'lmaganda kod ranglari uchun).
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import url from 'url';

const ROOT = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const HLJS = process.env.HLJS_DIR;

const browser = await chromium.launch();
const context = await browser.newContext({ colorScheme: 'light' });
if (HLJS) {
  await context.route(/cdnjs\.cloudflare\.com\/ajax\/libs\/highlight\.js\/[^/]+\/(.+)$/, (route) => {
    const rel = route.request().url().split('/highlight.js/')[1].split('/').slice(1).join('/');
    const file = path.join(HLJS, rel);
    if (fs.existsSync(file)) route.fulfill({ path: file });
    else route.abort();
  });
}
await context.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());   // shriftlar — tizimdagi Inter

const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

for (const job of jobs) {
  const page = await context.newPage();
  const src = url.pathToFileURL(path.join(ROOT, job.html || job.htmls[0])).href;
  const out = path.join(ROOT, job.pdf);
  fs.mkdirSync(path.dirname(out), { recursive: true });

  if (job.kind === 'deck') {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(src, { waitUntil: 'load' });
    await page.emulateMedia({ media: 'print' });
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    await page.pdf({ path: out, width: '1280px', height: '720px', printBackground: true, preferCSSPageSize: true });
  } else {
    await page.setViewportSize({ width: 1100, height: 1400 });
    try { await page.addInitScript(() => { try { localStorage.setItem('theme', 'light'); } catch (e) {} }); } catch (e) {}
    await page.goto(src, { waitUntil: 'load' });
    if (job.kind === 'combined') {
      // Qolgan darslarning <article> qismini birinchi sahifaga qo'shamiz — bitta hujjat, bitta shriftlar to'plami
      const articles = job.htmls.slice(1).map((h) => {
        const t = fs.readFileSync(path.join(ROOT, h), 'utf8');
        const m = t.match(/<article class="lesson">([\s\S]*)<\/article>/);
        return m ? m[1] : '';
      });
      await page.evaluate((list) => {
        const first = document.querySelector('article.lesson');
        let prev = first;
        for (const inner of list) {
          const a = document.createElement('article');
          a.className = 'lesson pdf-keyingi';
          a.innerHTML = inner;
          prev.after(a);
          prev = a;
        }
        if (window.hljs) document.querySelectorAll('pre code:not(.hljs)').forEach((el) => {
          el.className = el.className.replace(/\blanguage-jsx?\b/, 'language-javascript');
          try { hljs.highlightElement(el); } catch (e) {}
        });
      }, articles);
    }
    await page.evaluate(() => {
      document.documentElement.dataset.theme = 'light';
      document.querySelectorAll('details').forEach((d) => (d.open = true));
      document.querySelectorAll('.playground, .quiz-score, .pager').forEach((e) => e.remove());
      // Test javoblari — har bir dars oxirida alohida bo'lim
      document.querySelectorAll('article.lesson').forEach((art) => {
        const quizzes = [...art.querySelectorAll('.quiz')];
        if (!quizzes.length) return;
        const sec = document.createElement('section');
        sec.className = 'pdf-javoblar';
        const h = document.createElement('h3');
        h.textContent = '✅ Test javoblari';
        const ol = document.createElement('ol');
        quizzes.forEach((q) => {
          const n = Number(q.dataset.answer);
          const opts = [...q.querySelectorAll('ol > li')];
          const li = document.createElement('li');
          const b = document.createElement('b');
          b.textContent = `${'ABCDEF'[n - 1] || '?'}) ${opts[n - 1] ? opts[n - 1].textContent.trim() : ''}`;
          li.append((q.querySelector('.q')?.textContent.trim() || '') + ' — ', b);
          const ex = q.querySelector('.explain');
          if (ex) {
            const d = document.createElement('div');
            d.className = 'izoh';
            d.textContent = ex.textContent.trim();
            li.append(d);
          }
          ol.append(li);
        });
        sec.append(h, ol);
        art.append(sec);
      });
    });
    await page.emulateMedia({ media: 'print' });
    const title = esc(job.title || '');
    await page.pdf({
      path: out,
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `<div style="font-family:Inter,sans-serif;font-size:8px;color:#8a90a2;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>${title}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
      margin: { top: '14mm', bottom: '16mm', left: '13mm', right: '13mm' },
      outline: true,
    });
  }
  await page.close();
  process.stdout.write('.');
}
await browser.close();
console.log(`\n${jobs.length} ta PDF tayyor`);
