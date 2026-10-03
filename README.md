# web_fullstak — Web Full-Stack dasturlash asoslari

O'zbek tilidagi to'liq, bepul qo'llanma-sayt: noldan full-stack dasturchigacha.
Har bir dars **batafsil nazariya**, **3–4 ta real amaliy misol**, **mustaqil mashqlar** va **xulosadan** iborat.

## Darslar

| № | Mavzu | Asosiy tushunchalar |
|---|-------|---------------------|
| 01 | Web qanday ishlaydi | Mijoz-server, DNS, URL, HTTP metodlari va status kodlari, HTTPS, brauzer rendering |
| 02 | HTML | Semantik teglar, formalar, jadvallar, media, accessibility, SEO |
| 03 | CSS | Selektorlar, spetsifiklik, box model, Flexbox, Grid, responsiv dizayn, o'zgaruvchilar, animatsiya |
| 04 | JavaScript asoslari | Turlar, funksiyalar, scope va closure, massiv metodlari, obyektlar, sinflar, xatolar, modullar |
| 05 | DOM va hodisalar | Elementlarni boshqarish, hodisalar, bubbling va delegatsiya, formalar, localStorage |
| 06 | Asinxron JavaScript | Event loop, Promise, async/await, fetch, AbortController, retry |
| 07 | Git va GitHub | Commit, branch, merge, konfliktlar, Pull Request, GitHub Pages |
| 08 | Node.js va npm | Modullar, package.json, fs, path, events, streams, http, .env |
| 09 | Express.js va REST API | Marshrutlash, middleware, REST dizayni, Zod validatsiya, xatolarni boshqarish, fayl yuklash |
| 10 | Ma'lumotlar bazasi | SQL, JOIN, GROUP BY, normalizatsiya, indekslar, tranzaksiyalar, SQL injection, MongoDB |
| 11 | Autentifikatsiya | bcrypt, JWT, httpOnly cookie, himoyalangan marshrutlar, IDOR, RBAC |
| 12 | React | JSX, props, state, useEffect, custom hook'lar, Context, React Router |
| 13 | Yakuniy loyiha | PostgreSQL + Express + JWT + React "Eslatmalar" ilovasi bosqichma-bosqich |
| 14 | Deploy, xavfsizlik, test | Docker, Nginx, HTTPS, CI/CD, OWASP Top 10, node:test, Supertest, Vitest |

## Saytni ochish

- **Onlayn:** GitHub → Settings → Pages → *Deploy from a branch* → `main` / `(root)`.
  Sayt `https://oybekalloyorov.github.io/web_fullstak/` manzilida ochiladi.
- **Lokal:** `index.html` faylini brauzerda oching yoki `python3 -m http.server` buyrug'ini ishga tushiring.

## Loyiha tuzilmasi

```
├── index.html, darslar/*.html   # yig'ilgan (tayyor) sahifalar — GitHub Pages shularni ko'rsatadi
├── assets/css/style.css         # dizayn (kunduzgi/tungi rejim, responsiv)
├── assets/js/main.js            # menyu, qidiruv, nusxa olish, o'qish progressi
├── src/index.html               # bosh sahifa manbasi
├── src/darslar/NN-nom.html      # darslar manbasi
└── build.py                     # src/ → tayyor sahifalar (tashqi kutubxonasiz)
```

## Tahrirlash

1. `src/darslar/` ichidagi faylni o'zgartiring. Kod bloklarini xom holda yozing — `build.py` ularni o'zi ekranlaydi:
   ```html
   <pre data-lang="js" data-title="app.js">
   if (a < b && c) console.log('<b>ok</b>');
   </pre>
   ```
2. Yangi dars uchun `src/darslar/15-nom.html` yarating; boshida meta-blok bo'lsin:
   `<!-- title: ... | desc: ... | icon: 📘 | level: ... -->`
3. `python3 build.py` — sahifalar, yon menyu, mundarija va "oldingi/keyingi" havolalari qayta yig'iladi.

Xato topsangiz yoki taklifingiz bo'lsa — issue yoki pull request oching.
