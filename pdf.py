#!/usr/bin/env python3
"""
Saytdagi darslar va taqdimotlardan PDF fayllar yasaydi.

  darslar/NN-nom.html            -> darslar/pdf/NN-nom.pdf
  8-sinf/NN-nom.html             -> 8-sinf/pdf/NN-nom.pdf
  8-sinf/taqdimot/NN-nom.html    -> 8-sinf/taqdimot/pdf/NN-nom.pdf
  + har bir kurs uchun bitta umumiy PDF (sarlavhalar xatcho'p sifatida):
    darslar/pdf/full-stack-qollanma.pdf, 8-sinf/pdf/8-sinf-web-fullstack-kursi.pdf

Talablar: Node.js + Playwright (npm i playwright; npx playwright install chromium),
xatcho'plar uchun: pip install pypdf.
Avval sayt yig'ilgan bo'lishi kerak: python3 build.py && python3 slides.py

Ishga tushirish:  python3 pdf.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import build

ROOT = pathlib.Path(__file__).parent
COMBINED = {"darslar": "full-stack-qollanma.pdf", "8-sinf": "8-sinf-web-fullstack-kursi.pdf"}


def main():
    jobs = []
    for c in build.COURSES:
        lessons = build.load_lessons(c)
        for l in lessons:
            jobs.append({"html": f'{c["dir"]}/{l["slug"]}.html', "pdf": f'{c["dir"]}/pdf/{l["slug"]}.pdf',
                         "kind": "lesson", "title": f'{c["name"]} · {l["num"]}. {l["meta"].get("title", "")}'})
        jobs.append({"htmls": [f'{c["dir"]}/{l["slug"]}.html' for l in lessons],
                     "pdf": f'{c["dir"]}/pdf/{COMBINED[c["dir"]]}', "kind": "combined", "title": c["name"]})
    for t in sorted((ROOT / "8-sinf" / "taqdimot").glob("[0-9]*.html")):
        jobs.append({"html": f"8-sinf/taqdimot/{t.name}", "pdf": f"8-sinf/taqdimot/pdf/{t.stem}.pdf", "kind": "deck"})

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    subprocess.run(["node", str(ROOT / "tools" / "pdf_render.mjs"), f.name], check=True)

    for c in build.COURSES:
        xatchoplar(c, build.load_lessons(c))


def xatchoplar(course, lessons):
    """Umumiy PDF'ga har bir dars uchun xatcho'p (bookmark) qo'shadi. pypdf bo'lmasa — o'tkazib yuboradi."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print("  (pypdf yo'q — xatcho'plar qo'shilmadi: pip install pypdf)")
        return
    fayl = ROOT / course["dir"] / "pdf" / COMBINED[course["dir"]]
    reader = PdfReader(fayl)
    w = PdfWriter(clone_from=reader)
    qolgan = list(lessons)
    for i, page in enumerate(reader.pages):
        if not qolgan:
            break
        boshi = (page.extract_text() or "")[:200].lower()
        l = qolgan[0]
        if f'{l["num"]}-{course["unit"]}' in boshi:
            w.add_outline_item(f'{l["num"]}. {l["meta"].get("title", "")}', i)
            qolgan.pop(0)
    w.add_metadata({"/Title": course["name"]})
    with open(fayl, "wb") as fh:
        w.write(fh)
    print(f"  {fayl.relative_to(ROOT)}: {len(reader.pages)} bet, {len(lessons) - len(qolgan)} ta xatcho'p")

if __name__ == "__main__":
    sys.exit(main())
