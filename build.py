#!/usr/bin/env python3
"""
Qo'llanma saytini yig'uvchi skript (hech qanday tashqi kutubxona kerak emas).

  src/index.html              -> index.html               (umumiy bosh sahifa)
  src/darslar/NN-nom.html     -> darslar/NN-nom.html      ("Full-stack qo'llanma" kursi)
  src/8-sinf/index.html       -> 8-sinf/index.html        (8-sinf kursi bosh sahifasi)
  src/8-sinf/NN-nom.html      -> 8-sinf/NN-nom.html       (8-sinf o'quv dasturi mavzulari)

Manba fayllarda:
  * Boshida meta-blok:   <!-- title: ... | desc: ... | icon: ... | level: ... | bob: ... -->
  * Kod bloklari:        <pre data-lang="js"> ...xom kod... </pre>
    (ichidagi < > & belgilarini skript o'zi ekranlaydi)
    Qo'shimcha atributlar: data-title="fayl.js", data-play (HTML/CSS/JS ni brauzerda ishga tushirish)
  * <h2> sarlavhalarga avtomatik id beriladi va "Mundarija" yasaladi.

Ishga tushirish:  python3 build.py
"""
import html
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"

COURSES = [
    {
        "dir": "darslar",
        "name": "Full-stack qo'llanma",
        "unit": "dars",
        "home": "index.html",          # kurs ro'yxati qayerda (ildizga nisbatan)
    },
    {
        "dir": "8-sinf",
        "name": "8-sinf: Web Full-stack kursi",
        "unit": "mavzu",
        "home": "8-sinf/index.html",
    },
]

META_RE = re.compile(r"^\s*<!--(.*?)-->", re.S)
H2_RE = re.compile(r"<h2>(.*?)</h2>")
OPEN_RE = re.compile(r'<pre data-lang="([\w+-]+)"([^>]*)>\n?')
ATTR_RE = re.compile(r'([\w-]+)(?:="([^"]*)")?')

UZ_MAP = str.maketrans({"ʻ": "", "ʼ": "", "'": "", "‘": "", "’": ""})

LANG_NAMES = {
    "html": "HTML", "css": "CSS", "js": "JavaScript", "javascript": "JavaScript",
    "jsx": "React (JSX)", "bash": "Terminal", "json": "JSON", "sql": "SQL",
    "http": "HTTP", "text": "Matn", "dockerfile": "Dockerfile", "nginx": "Nginx",
    "ini": ".env", "yaml": "YAML", "plaintext": "Matn", "python": "Python",
    "py": "Python", "output": "Natija", "django": "Django shablon",
}


def slugify(text):
    text = re.sub(r"<.*?>", "", text).lower().translate(UZ_MAP)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "bolim"


def parse_meta(text):
    m = META_RE.match(text)
    meta = {}
    if m:
        for part in m.group(1).split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return meta, text


def render_code(lang, attrs, code):
    title = attrs.get("data-title")
    play = "data-play" in attrs
    label = title or LANG_NAMES.get(lang, lang)
    hl = {"py": "python", "output": "plaintext", "django": "html"}.get(lang, lang)
    cls = "code output" if lang == "output" else "code"
    play_btn = '<button class="run" type="button">▶ Sinab ko\'rish</button>' if play else ""
    return (
        f'<div class="{cls}"{" data-play" if play else ""}><div class="code-head"><span>{html.escape(label)}</span>'
        f'<span class="code-actions">{play_btn}<button class="copy" type="button">Nusxa olish</button></span></div>'
        f'<pre><code class="language-{hl}">{html.escape(code)}</code></pre></div>'
    )


def replace_code_blocks(body):
    """<pre data-lang> bloklarini almashtiradi; ichma-ich <pre> teglarini ham hisobga oladi."""
    out, pos = [], 0
    while True:
        m = OPEN_RE.search(body, pos)
        if not m:
            out.append(body[pos:])
            return "".join(out)
        out.append(body[pos:m.start()])
        depth, i = 1, m.end()
        while depth:
            nxt_open = body.find("<pre", i)
            nxt_close = body.find("</pre>", i)
            if nxt_close == -1:
                raise ValueError("Yopilmagan <pre> bloki: " + body[m.start():m.start() + 80])
            if nxt_open != -1 and nxt_open < nxt_close:
                depth, i = depth + 1, nxt_open + 4
            else:
                depth, i = depth - 1, nxt_close + 6
        code = body[m.end():i - 6]
        if code.endswith("\n"):
            code = code[:-1]
        attrs = {k: v for k, v in ATTR_RE.findall(m.group(2))}
        out.append(render_code(m.group(1), attrs, code))
        pos = i


def process_body(body):
    body = replace_code_blocks(body)
    toc = []
    used = set()

    def add_id(m):
        inner = m.group(1)
        sid = slugify(inner)
        base, i = sid, 2
        while sid in used:
            sid, i = f"{base}-{i}", i + 1
        used.add(sid)
        toc.append((sid, re.sub(r"<.*?>", "", inner)))
        return f'<h2 id="{sid}"><a class="anchor" href="#{sid}">#</a>{inner}</h2>'

    body = H2_RE.sub(add_id, body)
    return body, toc


def load_lessons(course):
    lessons = []
    for path in sorted((SRC / course["dir"]).glob("[0-9]*.html")):
        meta, body = parse_meta(path.read_text(encoding="utf-8"))
        num = path.stem.split("-", 1)[0]
        lessons.append({"slug": path.stem, "num": num, "meta": meta, "body": body})
    return lessons


def sidebar(course, lessons, current, prefix):
    """Yon menyu: bob (bo'lim) bo'yicha guruhlangan darslar ro'yxati."""
    items, last_bob = [], None
    for l in lessons:
        bob = l["meta"].get("bob")
        if bob and bob != last_bob:
            items.append(f'<li class="side-group">{html.escape(bob)}</li>')
            last_bob = bob
        cls = ' class="active"' if l["slug"] == current else ""
        items.append(
            f'<li><a{cls} href="{prefix}{course["dir"]}/{l["slug"]}.html">'
            f'<span class="num">{l["num"]}</span>{html.escape(l["meta"].get("title", l["slug"]))}</a></li>'
        )
    return "\n".join(items)


def course_switch(prefix, active_dir):
    links = []
    for c in COURSES:
        cls = ' class="active"' if c["dir"] == active_dir else ""
        links.append(f'<a{cls} href="{prefix}{c["home"]}">{html.escape(c["name"])}</a>')
    return '<nav class="course-switch">' + "".join(links) + "</nav>"


def page(title, desc, content, side, prefix, toc_html="", extra_class="", side_title="Darslar", active_dir=None):
    return f"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧭</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<link rel="stylesheet" href="{prefix}assets/css/style.css">
<script>document.documentElement.classList.add('js');try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
</head>
<body class="{extra_class}">
<div class="progress" id="progress"></div>
<header class="topbar">
  <button class="menu-btn" id="menuBtn" aria-label="Menyu">☰</button>
  <a class="brand" href="{prefix}index.html"><span class="logo">⟨/⟩</span> Full-Stack <b>Qo'llanma</b></a>
  <div class="top-actions">
    <input class="search" id="search" type="search" placeholder="Mavzu qidirish..." aria-label="Qidirish">
    <button class="theme-btn" id="themeBtn" aria-label="Mavzu rangini almashtirish">🌓</button>
  </div>
</header>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <a class="side-home" href="{prefix}index.html">🏠 Bosh sahifa</a>
    {course_switch(prefix, active_dir)}
    <div class="side-title">{html.escape(side_title)}</div>
    <ol class="lesson-list" id="lessonList">
{side}
    </ol>
  </aside>
  <main class="content">
{content}
  </main>
  {toc_html}
</div>
<div class="overlay" id="overlay"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="{prefix}assets/js/main.js"></script>
</body>
</html>
"""


def card(href, l, unit):
    m = l["meta"]
    return (
        f'<a class="card" href="{href}"><div class="card-icon">{m.get("icon", "📘")}</div>'
        f'<div class="card-num">{l["num"]}-{unit}</div><h3>{html.escape(m.get("title", ""))}</h3>'
        f'<p>{html.escape(m.get("desc", ""))}</p><div class="card-level">{html.escape(m.get("level", ""))}</div></a>'
    )


def cards_by_bob(lessons, unit):
    """Bob bo'yicha guruhlangan kartalar (kurs bosh sahifasi uchun)."""
    out, group, last = [], [], None
    for l in lessons:
        bob = l["meta"].get("bob", "")
        if bob != last and group:
            out.append(f'<h3 class="bob-title">{html.escape(last)}</h3><div class="cards">{"".join(group)}</div>')
            group = []
        last = bob
        group.append(card(f'{l["slug"]}.html', l, unit))
    if group:
        out.append(f'<h3 class="bob-title">{html.escape(last)}</h3><div class="cards">{"".join(group)}</div>')
    return "\n".join(out)


def build_course(course):
    lessons = load_lessons(course)
    out_dir = ROOT / course["dir"]
    out_dir.mkdir(exist_ok=True)
    unit = course["unit"]

    for i, l in enumerate(lessons):
        body, toc = process_body(l["body"])
        meta = l["meta"]
        title = meta.get("title", l["slug"])
        desc = meta.get("desc", "")
        prev_l = lessons[i - 1] if i > 0 else None
        next_l = lessons[i + 1] if i + 1 < len(lessons) else None
        nav = '<nav class="pager">'
        nav += (f'<a class="prev" href="{prev_l["slug"]}.html"><small>← Oldingi {unit}</small>'
                f'{html.escape(prev_l["meta"]["title"])}</a>') if prev_l else "<span></span>"
        nav += (f'<a class="next" href="{next_l["slug"]}.html"><small>Keyingi {unit} →</small>'
                f'{html.escape(next_l["meta"]["title"])}</a>') if next_l else "<span></span>"
        nav += "</nav>"
        crumb = f'{l["num"]}-{unit} · {len(lessons)} tadan'
        if meta.get("bob"):
            crumb += f' · {html.escape(meta["bob"])}'
        level = f'<div class="hero-level">{html.escape(meta["level"])}</div>' if meta.get("level") else ""
        header = (
            f'<div class="lesson-hero"><div class="hero-icon">{meta.get("icon", "📘")}</div>'
            f'<div><div class="crumb">{crumb}</div>'
            f'<h1>{html.escape(title)}</h1><p class="lead">{html.escape(desc)}</p>{level}</div></div>'
        )
        toc_html = (
            '<aside class="toc"><div class="toc-title">Ushbu sahifada</div><ul>'
            + "".join(f'<li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in toc)
            + "</ul></aside>"
        )
        content = f'<article class="lesson">{header}{body}{nav}</article>'
        out = page(f"{title} — {course['name']}", desc, content,
                   sidebar(course, lessons, l["slug"], "../"), "../", toc_html,
                   side_title=course["name"], active_dir=course["dir"])
        (out_dir / f"{l['slug']}.html").write_text(out, encoding="utf-8")

    # Kursning o'z bosh sahifasi (bo'lsa)
    course_index = SRC / course["dir"] / "index.html"
    if course_index.exists():
        meta, body = parse_meta(course_index.read_text(encoding="utf-8"))
        body = (body.replace("{{CARDS_BY_BOB}}", cards_by_bob(lessons, unit))
                    .replace("{{COUNT}}", str(len(lessons))))
        body, _ = process_body(body)
        out = page(meta.get("title", course["name"]), meta.get("desc", ""), body,
                   sidebar(course, lessons, None, "../"), "../", "", "home",
                   side_title=course["name"], active_dir=course["dir"])
        (out_dir / "index.html").write_text(out, encoding="utf-8")

    print(f"  {course['name']}: {len(lessons)} ta {unit}")
    return lessons


def build():
    all_lessons = {c["dir"]: build_course(c) for c in COURSES}

    # Umumiy bosh sahifa
    main = COURSES[0]
    lessons = all_lessons[main["dir"]]
    meta, body = parse_meta((SRC / "index.html").read_text(encoding="utf-8"))
    cards = "\n".join(card(f'{main["dir"]}/{l["slug"]}.html', l, main["unit"]) for l in lessons)
    body = body.replace("{{CARDS}}", cards).replace("{{COUNT}}", str(len(lessons)))
    for c in COURSES:
        body = body.replace("{{COUNT:%s}}" % c["dir"], str(len(all_lessons[c["dir"]])))
    body, _ = process_body(body)
    out = page(meta.get("title", "Full-Stack Qo'llanma"), meta.get("desc", ""), body,
               sidebar(main, lessons, None, ""), "", "", "home",
               side_title=main["name"], active_dir=None)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    print("Tayyor: barcha sahifalar yig'ildi.")


if __name__ == "__main__":
    build()
