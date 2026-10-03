#!/usr/bin/env python3
"""
Qo'llanma saytini yig'uvchi skript (hech qanday tashqi kutubxona kerak emas).

  src/index.html          -> index.html
  src/darslar/NN-nom.html -> darslar/NN-nom.html

Manba fayllarda:
  * Boshida meta-blok:   <!-- title: ... | desc: ... | icon: ... -->
  * Kod bloklari:        <pre data-lang="js"> ...xom kod... </pre>
    (ichidagi < > & belgilarini skript o'zi ekranlaydi)
  * <h2> sarlavhalarga avtomatik id beriladi va "Mundarija" yasaladi.

Ishga tushirish:  python3 build.py
"""
import html
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
OUT_LESSONS = ROOT / "darslar"

META_RE = re.compile(r"^\s*<!--(.*?)-->", re.S)
H2_RE = re.compile(r"<h2>(.*?)</h2>")

UZ_MAP = str.maketrans({"ʻ": "", "ʼ": "", "'": "", "‘": "", "’": ""})


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


def render_code(m):
    lang, title, code = m.group(1), m.group(2), m.group(3)
    label = title or LANG_NAMES.get(lang, lang)
    return (
        f'<div class="code"><div class="code-head"><span>{html.escape(label)}</span>'
        f'<button class="copy" type="button">Nusxa olish</button></div>'
        f'<pre><code class="language-{lang}">{html.escape(code)}</code></pre></div>'
    )


LANG_NAMES = {
    "html": "HTML", "css": "CSS", "js": "JavaScript", "javascript": "JavaScript",
    "jsx": "React (JSX)", "bash": "Terminal", "json": "JSON", "sql": "SQL",
    "http": "HTTP", "text": "Matn", "dockerfile": "Dockerfile", "nginx": "Nginx",
    "ini": ".env", "yaml": "YAML", "plaintext": "Matn",
}


OPEN_RE = re.compile(r'<pre data-lang="([\w+-]+)"(?: data-title="([^"]*)")?>\n?')


class _M:
    """render_code() uchun oddiy match-o'xshash obyekt."""
    def __init__(self, *groups):
        self.groups_ = groups

    def group(self, i):
        return self.groups_[i - 1]


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
        out.append(render_code(_M(m.group(1), m.group(2), code)))
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


def load_lessons():
    lessons = []
    for path in sorted((SRC / "darslar").glob("*.html")):
        meta, body = parse_meta(path.read_text(encoding="utf-8"))
        num = path.stem.split("-", 1)[0]
        lessons.append({"path": path, "slug": path.stem, "num": num, "meta": meta, "body": body})
    return lessons


def sidebar(lessons, current, prefix):
    items = []
    for l in lessons:
        cls = ' class="active"' if l["slug"] == current else ""
        items.append(
            f'<li><a{cls} href="{prefix}darslar/{l["slug"]}.html">'
            f'<span class="num">{l["num"]}</span>{html.escape(l["meta"].get("title", l["slug"]))}</a></li>'
        )
    return "\n".join(items)


def page(title, desc, content, side, prefix, toc_html="", extra_class=""):
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
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
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
    <div class="side-title">Darslar</div>
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


def build():
    lessons = load_lessons()
    OUT_LESSONS.mkdir(exist_ok=True)

    for i, l in enumerate(lessons):
        body, toc = process_body(l["body"])
        title = l["meta"].get("title", l["slug"])
        desc = l["meta"].get("desc", "")
        icon = l["meta"].get("icon", "📘")
        prev_l = lessons[i - 1] if i > 0 else None
        next_l = lessons[i + 1] if i + 1 < len(lessons) else None
        nav = '<nav class="pager">'
        nav += (f'<a class="prev" href="{prev_l["slug"]}.html"><small>← Oldingi dars</small>'
                f'{html.escape(prev_l["meta"]["title"])}</a>') if prev_l else "<span></span>"
        nav += (f'<a class="next" href="{next_l["slug"]}.html"><small>Keyingi dars →</small>'
                f'{html.escape(next_l["meta"]["title"])}</a>') if next_l else "<span></span>"
        nav += "</nav>"
        header = (
            f'<div class="lesson-hero"><div class="hero-icon">{icon}</div>'
            f'<div><div class="crumb">{l["num"]}-dars · {len(lessons)} tadan</div>'
            f'<h1>{html.escape(title)}</h1><p class="lead">{html.escape(desc)}</p></div></div>'
        )
        toc_html = (
            '<aside class="toc"><div class="toc-title">Ushbu sahifada</div><ul>'
            + "".join(f'<li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in toc)
            + "</ul></aside>"
        )
        content = f'<article class="lesson">{header}{body}{nav}</article>'
        out = page(f"{title} — Full-Stack Qo'llanma", desc, content,
                   sidebar(lessons, l["slug"], "../"), "../", toc_html)
        (OUT_LESSONS / f"{l['slug']}.html").write_text(out, encoding="utf-8")

    # Bosh sahifa
    meta, body = parse_meta((SRC / "index.html").read_text(encoding="utf-8"))
    cards = []
    for l in lessons:
        m = l["meta"]
        cards.append(
            f'<a class="card" href="darslar/{l["slug"]}.html"><div class="card-icon">{m.get("icon", "📘")}</div>'
            f'<div class="card-num">{l["num"]}-dars</div><h3>{html.escape(m.get("title", ""))}</h3>'
            f'<p>{html.escape(m.get("desc", ""))}</p><div class="card-level">{html.escape(m.get("level", ""))}</div></a>'
        )
    body = body.replace("{{CARDS}}", "\n".join(cards)).replace("{{COUNT}}", str(len(lessons)))
    body, _ = process_body(body)
    out = page(meta.get("title", "Full-Stack Qo'llanma"), meta.get("desc", ""), body,
               sidebar(lessons, None, ""), "", "", "home")
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    print(f"Tayyor: {len(lessons)} ta dars + bosh sahifa yig'ildi.")


if __name__ == "__main__":
    build()
