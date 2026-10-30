#!/usr/bin/env python3
"""
admin_panel.py — O'qituvchi uchun Web Admin Panel (Flask + PostgreSQL).

Imkoniyatlari:
  1. Natijalar monitoringi: kim qaysi testdan qancha ball va necha foiz olganini ko'rish,
     har bir o'quvchining javoblarini tahlil qilish hamda CSV/Excel formatda yuklab olish.
  2. O'quvchilar boshqaruvi: har bir o'quvchi uchun F.I.Sh, sinf hamda alohida Login va Parol kiritish/tahrirlash.
  3. Test yaratish: o'qituvchi qaysi va nechta mavzular bo'yicha test bo'lishini, nechta savol tushishini
     va har bir savol necha ball berishini belgilaydi.
  4. Mavzular va savollar bazasi: `web_fullstak` qo'llanmasidagi 82 ta mavzu va 495+ savolni sinxronlash
     hamda yangi savollar qo'shish.

Ishga tushirish:
  python3 admin_panel.py
"""

import csv
import io
import os
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

import database as db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "web-fullstak-secret-key-2026")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


# =====================================================================
# HTML SHABLONLAR (Bootstrap 5 asosida zamonaviy interfeys)
# =====================================================================

BASE_LAYOUT = """
<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title or "O'qituvchi Admin Paneli — web_fullstak Test Tizimi" }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background-color: #f4f6fb; font-family: system-ui, -apple-system, sans-serif; }
    .navbar { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); }
    .stat-card { border: none; border-radius: 14px; box-shadow: 0 4px 14px rgba(15,23,42,0.06); }
    .content-card { border: none; border-radius: 14px; box-shadow: 0 4px 16px rgba(15,23,42,0.05); background: #fff; }
    .topic-box { max-height: 420px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
    .badge-course { font-size: 0.78rem; }
    code.cred { background: #eef2ff; color: #3730a3; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark mb-4 py-3">
  <div class="container">
    <a class="navbar-brand fw-bold" href="{{ url_for('dashboard') }}">
      🎓 web_fullstak — O'qituvchi Test Paneli
    </a>
    {% if session.get('is_admin') %}
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0 ms-lg-4 gap-1">
        <li class="nav-item">
          <a class="nav-link {% if active_tab == 'results' %}active fw-semibold{% endif %}" href="{{ url_for('dashboard') }}">
            📊 Natijalar va Ballar
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link {% if active_tab == 'students' %}active fw-semibold{% endif %}" href="{{ url_for('students_page') }}">
            👨‍🎓 O'quvchilar (Login / Parol)
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link {% if active_tab == 'exams' %}active fw-semibold{% endif %}" href="{{ url_for('exams_page') }}">
            📝 Testlar va Mavzularni tanlash
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link {% if active_tab == 'topics' %}active fw-semibold{% endif %}" href="{{ url_for('topics_page') }}">
            📚 Qo'llanma savollari ({{ stats.questions_count if stats else '' }})
          </a>
        </li>
      </ul>
      <div class="d-flex gap-2">
        <form method="post" action="{{ url_for('sync_html_route') }}" class="m-0">
          <button type="submit" class="btn btn-outline-light btn-sm">🔄 Qo'llanmadan sinxronlash</button>
        </form>
        <a href="{{ url_for('logout') }}" class="btn btn-danger btn-sm">Chiqish</a>
      </div>
    </div>
    {% endif %}
  </div>
</nav>

<div class="container pb-5">
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, msg in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm" role="alert">
          {{ msg }}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {{ body_html | safe }}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


def render_page(body_template: str, **context) -> str:
    try:
        context.setdefault("stats", db.get_dashboard_stats())
    except Exception:
        context.setdefault("stats", None)
    inner = render_template_string(body_template, **context)
    return render_template_string(BASE_LAYOUT, body_html=inner, **context)


# =====================================================================
# 1. KIRISH VA CHIQISH (ADMIN LOGIN)
# =====================================================================

LOGIN_HTML = """
<div class="row justify-content-center mt-5">
  <div class="col-md-5 col-lg-4">
    <div class="card content-card p-4">
      <h4 class="fw-bold text-center mb-2">🔐 O'qituvchi kabineti</h4>
      <p class="text-muted text-center small mb-4">Testlar, mavzular va o'quvchilar ballarini boshqarish</p>
      <form method="post">
        <div class="mb-3">
          <label class="form-label fw-semibold">Admin login</label>
          <input type="text" name="username" class="form-control" required autofocus placeholder="admin">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Admin parol</label>
          <input type="password" name="password" class="form-control" required placeholder="••••••••">
        </div>
        <button type="submit" class="btn btn-primary w-100 fw-semibold py-2">Tizimga kirish</button>
      </form>
    </div>
  </div>
</div>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Xush kelibsiz! Admin panelga muvaffaqiyatli kirdingiz.", "success")
            return redirect(url_for("dashboard"))
        flash("Login yoki parol noto'g'ri!", "danger")
    return render_page(LOGIN_HTML, page_title="Kirish — Admin Panel")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/sync-html", methods=["POST"])
@login_required
def sync_html_route():
    res = db.seed_topics_and_questions()
    flash(
        f"✅ Qo'llanma savollari yangilandi: {res['topics']} ta mavzu, {res['questions']} ta test savoli bazaga yuklandi!",
        "success",
    )
    return redirect(request.referrer or url_for("dashboard"))


# =====================================================================
# 2. BOSH SAHIFA: KIM QANCHA BALL OLGANINI KO'RISH (NATIJALAR)
# =====================================================================

DASHBOARD_HTML = """
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3">
    <div class="card stat-card p-3 bg-white">
      <div class="text-muted small">Jami o'quvchilar</div>
      <div class="fs-3 fw-bold text-primary">{{ stats.students_count }} ta</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card p-3 bg-white">
      <div class="text-muted small">Faol testlar</div>
      <div class="fs-3 fw-bold text-success">{{ stats.active_exams_count }} ta</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card p-3 bg-white">
      <div class="text-muted small">Mavzular / Savollar</div>
      <div class="fs-3 fw-bold text-dark">{{ stats.topics_count }} / {{ stats.questions_count }}</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="card stat-card p-3 bg-white">
      <div class="text-muted small">Topshirilgan testlar</div>
      <div class="fs-3 fw-bold text-indigo">{{ stats.completed_attempts_count }} ta</div>
    </div>
  </div>
</div>

<div class="card content-card p-4">
  <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
    <div>
      <h5 class="fw-bold mb-0">🏆 O'quvchilarning test natijalari va olgan ballari</h5>
      <small class="text-muted">Har bir o'quvchining ishlagan testi, to'g'ri javoblari va to'plagan bali</small>
    </div>
    <a href="{{ url_for('export_results_csv', exam_id=selected_exam or '', class_name=selected_class or '', q=search_q or '') }}"
       class="btn btn-success btn-sm fw-semibold">
      📥 Excel / CSV yuklab olish
    </a>
  </div>

  <form method="get" class="row g-2 mb-4">
    <div class="col-md-4">
      <select name="exam_id" class="form-select form-select-sm" onchange="this.form.submit()">
        <option value="">— Barcha testlar —</option>
        {% for ex in exams %}
          <option value="{{ ex.id }}" {% if selected_exam == ex.id|string %}selected{% endif %}>
            {{ ex.title }} ({{ ex.topic_count }} mavzu, {{ ex.question_count }} savol)
          </option>
        {% endfor %}
      </select>
    </div>
    <div class="col-md-3">
      <select name="class_name" class="form-select form-select-sm" onchange="this.form.submit()">
        <option value="">— Barcha sinflar —</option>
        {% for c in stats.classes %}
          <option value="{{ c }}" {% if selected_class == c %}selected{% endif %}>{{ c }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="col-md-3">
      <input type="text" name="q" value="{{ search_q or '' }}" class="form-control form-control-sm"
             placeholder="O'quvchi F.I.Sh yoki login...">
    </div>
    <div class="col-md-2 d-flex gap-1">
      <button type="submit" class="btn btn-primary btn-sm w-100">Filtrlash</button>
      <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary btn-sm">Tozalash</a>
    </div>
  </form>

  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0">
      <thead class="table-light">
        <tr>
          <th>#</th>
          <th>O'quvchi F.I.Sh</th>
          <th>Sinf</th>
          <th>Login</th>
          <th>Test nomi</th>
          <th>To'g'ri javob</th>
          <th>To'plagan bali</th>
          <th>Foiz / Baho</th>
          <th>Holati</th>
          <th>Vaqt</th>
          <th>Tahlil</th>
        </tr>
      </thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td>{{ loop.index }}</td>
          <td class="fw-semibold">{{ r.full_name }}</td>
          <td><span class="badge bg-secondary">{{ r.class_name }}</span></td>
          <td><code class="cred">{{ r.login }}</code></td>
          <td>
            <div class="fw-medium">{{ r.exam_title }}</div>
            <small class="text-muted">{{ r.topic_count }} ta mavzu bo'yicha</small>
          </td>
          <td>
            <span class="fw-bold">{{ r.correct_answers }}</span> / {{ r.total_questions }}
          </td>
          <td>
            <span class="fs-6 fw-bold text-primary">{{ r.score_points }}</span>
            <small class="text-muted">/ {{ r.max_points }} ball</small>
          </td>
          <td>
            {% if r.percentage >= 86 %}
              <span class="badge bg-success">{{ r.percentage }}% (5 - A'lo)</span>
            {% elif r.percentage >= 71 %}
              <span class="badge bg-primary">{{ r.percentage }}% (4 - Yaxshi)</span>
            {% elif r.percentage >= 55 %}
              <span class="badge bg-warning text-dark">{{ r.percentage }}% (3 - Qoniqarli)</span>
            {% else %}
              <span class="badge bg-danger">{{ r.percentage }}% (2 - Qoniqarsiz)</span>
            {% endif %}
          </td>
          <td>
            {% if r.status == 'completed' %}
              <span class="badge bg-success-subtle text-success">Yakunlangan</span>
            {% else %}
              <span class="badge bg-warning-subtle text-warning">Ishlanmoqda...</span>
            {% endif %}
          </td>
          <td class="small text-muted">
            {{ r.finished_at.strftime('%d.%m.%Y %H:%M') if r.finished_at else r.started_at.strftime('%d.%m.%Y %H:%M') }}
          </td>
          <td>
            <a href="{{ url_for('attempt_detail_page', attempt_id=r.attempt_id) }}"
               class="btn btn-outline-primary btn-sm">👁 Ko'rish</a>
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="11" class="text-center text-muted py-4">
            Hozircha test natijalari yo'q. O'quvchilar Telegram bot orqali test ishlashi bilan shu yerda ko'rinadi.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""


@app.route("/")
@login_required
def dashboard():
    exam_id = request.args.get("exam_id", "").strip()
    class_name = request.args.get("class_name", "").strip()
    search_q = request.args.get("q", "").strip()

    results = db.list_all_results(
        exam_id=int(exam_id) if exam_id.isdigit() else None,
        class_name=class_name or None,
        search=search_q or None,
    )
    exams = db.list_exams()
    return render_page(
        DASHBOARD_HTML,
        active_tab="results",
        results=results,
        exams=exams,
        selected_exam=exam_id,
        selected_class=class_name,
        search_q=search_q,
    )


@app.route("/results/export")
@login_required
def export_results_csv():
    exam_id = request.args.get("exam_id", "").strip()
    class_name = request.args.get("class_name", "").strip()
    search_q = request.args.get("q", "").strip()

    results = db.list_all_results(
        exam_id=int(exam_id) if exam_id.isdigit() else None,
        class_name=class_name or None,
        search=search_q or None,
    )

    output = io.StringIO()
    output.write("\ufeff")  # Excel UTF-8 BOM
    writer = csv.writer(output)
    writer.writerow([
        "T/r",
        "O'quvchi F.I.Sh",
        "Sinf",
        "Login",
        "Test nomi",
        "To'g'ri javoblar",
        "Jami savollar",
        "To'plagan bali",
        "Maksimal ball",
        "Foiz (%)",
        "Holati",
        "Topshirgan vaqti",
    ])
    for idx, r in enumerate(results, 1):
        writer.writerow([
            idx,
            r["full_name"],
            r["class_name"],
            r["login"],
            r["exam_title"],
            r["correct_answers"],
            r["total_questions"],
            r["score_points"],
            r["max_points"],
            r["percentage"],
            r["status"],
            r["finished_at"].strftime("%Y-%m-%d %H:%M") if r["finished_at"] else "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test_natijalari.csv"},
    )


ATTEMPT_DETAIL_HTML = """
<div class="mb-3">
  <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary btn-sm">← Natijalarga qaytish</a>
</div>
<div class="card content-card p-4 mb-4">
  <div class="d-flex flex-wrap justify-content-between align-items-center">
    <div>
      <h5 class="fw-bold mb-1">{{ detail.full_name }} ({{ detail.class_name }}) — <code class="cred">{{ detail.login }}</code></h5>
      <p class="text-muted mb-0">Test: <b>{{ detail.exam_title }}</b></p>
    </div>
    <div class="text-end">
      <div class="fs-4 fw-bold text-primary">{{ detail.score_points }} / {{ detail.max_points }} ball ({{ detail.percentage }}%)</div>
      <div class="small text-muted">To'g'ri javoblar: {{ detail.correct_answers }} / {{ detail.total_questions }} ta</div>
    </div>
  </div>
</div>

<div class="card content-card p-4">
  <h6 class="fw-bold mb-3">Savollar bo'yicha javoblar tahlili</h6>
  {% for a in detail.answers %}
    <div class="border rounded-3 p-3 mb-3 {% if a.is_correct %}border-success bg-success-subtle{% else %}border-danger bg-danger-subtle{% endif %} bg-opacity-10">
      <div class="d-flex justify-content-between mb-1">
        <span class="fw-bold">{{ a.question_order }}-savol. {{ a.question_text }}</span>
        <span class="badge bg-dark">{{ a.topic_title }}</span>
      </div>
      <ol class="mb-1">
        {% for opt in [a.option_a, a.option_b, a.option_c, a.option_d] %}
          <li class="{% if loop.index == a.correct_option %}fw-bold text-success{% elif loop.index == a.selected_option and not a.is_correct %}fw-bold text-danger text-decoration-line-through{% endif %}">
            {{ opt }}
            {% if loop.index == a.correct_option %} ✅ (To'g'ri javob){% endif %}
            {% if loop.index == a.selected_option and not a.is_correct %} ❌ (O'quvchi tanlagan){% endif %}
          </li>
        {% endfor %}
      </ol>
      {% if a.explanation %}
        <div class="small text-muted mt-1">💡 <i>{{ a.explanation }}</i></div>
      {% endif %}
    </div>
  {% endfor %}
</div>
"""


@app.route("/results/<int:attempt_id>")
@login_required
def attempt_detail_page(attempt_id: int):
    detail = db.get_attempt_detail(attempt_id)
    if not detail:
        flash("Natija topilmadi.", "warning")
        return redirect(url_for("dashboard"))
    return render_page(ATTEMPT_DETAIL_HTML, active_tab="results", detail=detail)


# =====================================================================
# 3. O'QUVCHILAR VA ALOHIDA LOGIN / PAROL BOSHQARUVI
# =====================================================================

STUDENTS_HTML = """
<div class="row g-4">
  <div class="col-lg-4">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-1">➕ O'quvchi qo'shish</h5>
      <p class="text-muted small mb-3">Har bir o'quvchi uchun alohida login va parol belgilang</p>
      <form method="post" action="{{ url_for('add_student_route') }}">
        <div class="mb-3">
          <label class="form-label fw-semibold">O'quvchi F.I.Sh</label>
          <input type="text" name="full_name" class="form-control" required placeholder="Masalan: Aliyev Vali">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Sinf yoki guruh</label>
          <input type="text" name="class_name" class="form-control" required value="8-A sinf" placeholder="8-A sinf">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Shaxsiy Login</label>
          <div class="input-group">
            <input type="text" id="newLogin" name="login" class="form-control" required placeholder="aliyev_vali">
            <button type="button" class="btn btn-outline-secondary" onclick="genLogin()">Avto</button>
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Shaxsiy Parol</label>
          <div class="input-group">
            <input type="text" id="newPass" name="password" class="form-control" required placeholder="Kamida 4 ta belgi">
            <button type="button" class="btn btn-outline-secondary" onclick="genPass()">🎲 Generatsiya</button>
          </div>
        </div>
        <button type="submit" class="btn btn-primary w-100 fw-semibold">Saqlash va login berish</button>
      </form>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card content-card p-4">
      <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
        <h5 class="fw-bold mb-0">👨‍🎓 O'quvchilar va ularning Login-Parollari ({{ students|length }} ta)</h5>
        <form method="get" class="d-flex gap-2">
          <input type="text" name="q" value="{{ search_q or '' }}" class="form-control form-control-sm" placeholder="Ism yoki login qidirish...">
          <button type="submit" class="btn btn-outline-primary btn-sm">Qidirish</button>
        </form>
      </div>

      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead class="table-light">
            <tr>
              <th>#</th>
              <th>O'quvchi F.I.Sh</th>
              <th>Sinf</th>
              <th>Login</th>
              <th>Parol</th>
              <th>Telegram holati</th>
              <th>Testlar / O'rtacha</th>
              <th>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {% for s in students %}
            <tr>
              <td>{{ loop.index }}</td>
              <td class="fw-semibold">{{ s.full_name }}</td>
              <td><span class="badge bg-secondary">{{ s.class_name }}</span></td>
              <td><code class="cred">{{ s.login }}</code></td>
              <td><code class="cred">{{ s.plain_password }}</code></td>
              <td>
                {% if s.telegram_id %}
                  <span class="badge bg-success-subtle text-success">
                    ✅ Ulangan {% if s.telegram_username %}(@{{ s.telegram_username }}){% endif %}
                  </span>
                {% else %}
                  <span class="badge bg-light text-muted border">⏳ Kutilmoqda</span>
                {% endif %}
              </td>
              <td>
                {{ s.completed_exams }} ta ({{ s.avg_percent }}%)
              </td>
              <td>
                <div class="d-flex gap-1">
                  <button type="button" class="btn btn-outline-primary btn-sm"
                          data-bs-toggle="modal" data-bs-target="#editModal{{ s.id }}">✏️</button>
                  {% if s.telegram_id %}
                  <form method="post" action="{{ url_for('unlink_student_route', student_id=s.id) }}" class="m-0"
                        title="Telegram bog'lanishini uzish">
                    <button type="submit" class="btn btn-outline-warning btn-sm">🔓</button>
                  </form>
                  {% endif %}
                  <form method="post" action="{{ url_for('delete_student_route', student_id=s.id) }}" class="m-0"
                        onsubmit="return confirm('O\\'quvchini o\\'chirishni tasdiqlaysizmi?');">
                    <button type="submit" class="btn btn-outline-danger btn-sm">🗑</button>
                  </form>
                </div>

                <!-- Tahrirlash Modal -->
                <div class="modal fade" id="editModal{{ s.id }}" tabindex="-1">
                  <div class="modal-dialog">
                    <form method="post" action="{{ url_for('edit_student_route', student_id=s.id) }}" class="modal-content">
                      <div class="modal-header">
                        <h5 class="modal-title fw-bold">O'quvchi login-parolini tahrirlash</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                      </div>
                      <div class="modal-body">
                        <div class="mb-3">
                          <label class="form-label">F.I.Sh</label>
                          <input type="text" name="full_name" class="form-control" value="{{ s.full_name }}" required>
                        </div>
                        <div class="mb-3">
                          <label class="form-label">Sinf</label>
                          <input type="text" name="class_name" class="form-control" value="{{ s.class_name }}" required>
                        </div>
                        <div class="mb-3">
                          <label class="form-label">Login</label>
                          <input type="text" name="login" class="form-control" value="{{ s.login }}" required>
                        </div>
                        <div class="mb-3">
                          <label class="form-label">Parol</label>
                          <input type="text" name="password" class="form-control" value="{{ s.plain_password }}" required>
                        </div>
                        <div class="form-check">
                          <input class="form-check-input" type="checkbox" name="is_active" id="act{{ s.id }}"
                                 {% if s.is_active %}checked{% endif %}>
                          <label class="form-check-label" for="act{{ s.id }}">Faol (test ishlashiga ruxsat berilgan)</label>
                        </div>
                      </div>
                      <div class="modal-footer">
                        <button type="submit" class="btn btn-primary">Saqlash</button>
                      </div>
                    </form>
                  </div>
                </div>
              </td>
            </tr>
            {% else %}
            <tr>
              <td colspan="8" class="text-center text-muted py-4">Hozircha o'quvchilar kiritilmagan. Chap tomondagi forma orqali qo'shing.</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
function genPass() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  let out = '';
  for (let i = 0; i < 6; i++) out += chars.charAt(Math.floor(Math.random() * chars.length));
  document.getElementById('newPass').value = out;
}
function genLogin() {
  const nameInput = document.querySelector('input[name="full_name"]').value.trim().toLowerCase();
  const base = nameInput.replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'oquvchi';
  const rand = Math.floor(100 + Math.random() * 900);
  document.getElementById('newLogin').value = base + '_' + rand;
}
</script>
"""


@app.route("/students")
@login_required
def students_page():
    search_q = request.args.get("q", "").strip()
    students = db.list_students(search=search_q or None)
    return render_page(
        STUDENTS_HTML,
        active_tab="students",
        students=students,
        search_q=search_q,
    )


@app.route("/students/add", methods=["POST"])
@login_required
def add_student_route():
    try:
        s = db.create_student(
            full_name=request.form.get("full_name", ""),
            class_name=request.form.get("class_name", "8-sinf"),
            login=request.form.get("login", ""),
            password=request.form.get("password", ""),
        )
        flash(
            f"✅ O'quvchi qo'shildi: {s['full_name']} | Login: {s['login']} | Parol: {s['plain_password']}",
            "success",
        )
    except Exception as e:
        flash(f"❌ Xatolik (bunday login mavjud bo'lishi mumkin): {e}", "danger")
    return redirect(url_for("students_page"))


@app.route("/students/<int:student_id>/edit", methods=["POST"])
@login_required
def edit_student_route(student_id: int):
    try:
        db.update_student(
            student_id=student_id,
            full_name=request.form.get("full_name", ""),
            class_name=request.form.get("class_name", ""),
            login=request.form.get("login", ""),
            password=request.form.get("password", ""),
            is_active=bool(request.form.get("is_active")),
        )
        flash("✅ O'quvchi ma'lumotlari va login-paroli yangilandi.", "success")
    except Exception as e:
        flash(f"❌ Yangilashda xatolik: {e}", "danger")
    return redirect(url_for("students_page"))


@app.route("/students/<int:student_id>/unlink", methods=["POST"])
@login_required
def unlink_student_route(student_id: int):
    db.unlink_student_telegram(student_id)
    flash("🔓 O'quvchining Telegram akkaunti bog'lanishdan uzildi.", "info")
    return redirect(url_for("students_page"))


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student_route(student_id: int):
    db.delete_student(student_id)
    flash("🗑 O'quvchi o'chirildi.", "warning")
    return redirect(url_for("students_page"))


# =====================================================================
# 4. O'QITUVCHI TEST YARATISHI (QAYSI VA NECHTA MAVZULAR BO'YICHA)
# =====================================================================

EXAMS_HTML = """
<div class="row g-4">
  <div class="col-lg-6">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-1">📝 Yangi test yaratish</h5>
      <p class="text-muted small mb-3">
        Qaysi va nechta mavzular bo'yicha test olinishini belgilang — bot shu mavzulardan tasodifiy savol tushiradi
      </p>

      <form method="post" action="{{ url_for('create_exam_route') }}">
        <div class="mb-3">
          <label class="form-label fw-semibold">Test nomi</label>
          <input type="text" name="title" class="form-control" required
                 placeholder="Masalan: 8-sinf I bob (HTML va CSS) nazorat testi">
        </div>

        <div class="row g-2 mb-3">
          <div class="col-md-4">
            <label class="form-label fw-semibold">Tushadigan savollar soni</label>
            <input type="number" name="question_count" id="qCountInput" class="form-control" value="15" min="1" max="200" required>
          </div>
          <div class="col-md-4">
            <label class="form-label fw-semibold">1 ta savol bali</label>
            <input type="number" step="0.5" name="points_per_question" class="form-control" value="5" min="0.5" required>
          </div>
          <div class="col-md-4">
            <label class="form-label fw-semibold">Urinishlar soni</label>
            <input type="number" name="max_attempts" class="form-control" value="1" min="1" max="10" required>
          </div>
        </div>

        <div class="mb-2 d-flex flex-wrap justify-content-between align-items-center gap-1">
          <label class="form-label fw-semibold mb-0">
            Mavzularni tanlang:
            <span class="badge bg-primary ms-1" id="selectedSummary">0 ta mavzu (0 ta savol bazada)</span>
          </label>
          <div class="btn-group btn-group-sm">
            <button type="button" class="btn btn-outline-secondary" onclick="toggleCourse('8-sinf', true)">8-sinf Web</button>
            <button type="button" class="btn btn-outline-secondary" onclick="toggleCourse('cs', true)">8-sinf CS</button>
            <button type="button" class="btn btn-outline-secondary" onclick="toggleCourse('darslar', true)">Full-stack</button>
            <button type="button" class="btn btn-outline-danger" onclick="clearAllTopics()">Tozalash</button>
          </div>
        </div>

        <div class="topic-box mb-3">
          {% for course_dir, course_topics in grouped_topics.items() %}
            <div class="mb-3">
              <div class="fw-bold text-primary border-bottom pb-1 mb-2 d-flex justify-content-between align-items-center">
                <span>📘 {{ course_topics[0].course_name }} ({{ course_topics|length }} mavzu)</span>
                <button type="button" class="btn btn-link btn-sm p-0 text-decoration-none"
                        onclick="toggleCourse('{{ course_dir }}', true)">Barchasini belgilash</button>
              </div>
              {% for t in course_topics %}
                <div class="form-check py-1">
                  <input class="form-check-input topic-checkbox" type="checkbox"
                         name="topic_ids" value="{{ t.id }}"
                         id="t_{{ t.id }}"
                         data-course="{{ t.course_dir }}"
                         data-qcount="{{ t.question_count }}"
                         onchange="updateSelectedTopics()">
                  <label class="form-check-label small d-flex justify-content-between" for="t_{{ t.id }}">
                    <span><b>{{ "%02d"|format(t.topic_number) }}.</b> {{ t.title }}</span>
                    <span class="badge bg-secondary-subtle text-dark ms-2">{{ t.question_count }} savol</span>
                  </label>
                </div>
              {% endfor %}
            </div>
          {% endfor %}
        </div>

        <button type="submit" class="btn btn-primary w-100 fw-semibold py-2">
          ✅ Testni yaratish va o'quvchilarga ochish
        </button>
      </form>
    </div>
  </div>

  <div class="col-lg-6">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-3">📋 Mavjud testlar ({{ exams|length }} ta)</h5>
      {% for ex in exams %}
        <div class="border rounded-3 p-3 mb-3 {% if ex.is_active %}border-primary-subtle bg-white{% else %}bg-light text-muted{% endif %}">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div>
              <h6 class="fw-bold mb-1">
                {{ ex.title }}
                {% if ex.is_active %}
                  <span class="badge bg-success">Faol</span>
                {% else %}
                  <span class="badge bg-secondary">Yopiq</span>
                {% endif %}
              </h6>
              <div class="small text-muted mb-2">
                📚 <b>{{ ex.topic_count }} ta mavzu</b> •
                ❓ <b>{{ ex.question_count }} ta savol</b> •
                🏆 Har bir savol: <b>{{ ex.points_per_question }} ball</b> (Maks: {{ (ex.question_count * ex.points_per_question)|round(1) }} ball) •
                👨‍🎓 Topshirdi: <b>{{ ex.completed_count }} kishi</b>
              </div>
              <details class="small">
                <summary class="text-primary" style="cursor:pointer">Tanlangan mavzularni ko'rish ({{ ex.topic_count }} ta)</summary>
                <div class="mt-1 text-muted">{{ ex.topics_summary }}</div>
              </details>
            </div>
            <div class="d-flex gap-1">
              <form method="post" action="{{ url_for('toggle_exam_route', exam_id=ex.id) }}" class="m-0">
                <button type="submit" class="btn btn-sm {% if ex.is_active %}btn-outline-warning{% else %}btn-outline-success{% endif %}">
                  {% if ex.is_active %}⏸ To'xtatish{% else %}▶ Yoqish{% endif %}
                </button>
              </form>
              <form method="post" action="{{ url_for('delete_exam_route', exam_id=ex.id) }}" class="m-0"
                    onsubmit="return confirm('Testni o\\'chirishni tasdiqlaysizmi?');">
                <button type="submit" class="btn btn-outline-danger btn-sm">🗑</button>
              </form>
            </div>
          </div>
        </div>
      {% else %}
        <p class="text-muted text-center py-4 mb-0">Hozircha test yaratilmagan. Chap tomondan mavzularni belgilab test oching.</p>
      {% endfor %}
    </div>
  </div>
</div>

<script>
function updateSelectedTopics() {
  const checked = document.querySelectorAll('.topic-checkbox:checked');
  let totalQ = 0;
  checked.forEach(cb => { totalQ += parseInt(cb.dataset.qcount || '0', 10); });
  document.getElementById('selectedSummary').textContent =
    checked.length + ' ta mavzu (' + totalQ + ' ta savol bazada)';
}
function toggleCourse(courseDir, state) {
  document.querySelectorAll('.topic-checkbox[data-course="' + courseDir + '"]').forEach(cb => {
    cb.checked = state;
  });
  updateSelectedTopics();
}
function clearAllTopics() {
  document.querySelectorAll('.topic-checkbox').forEach(cb => { cb.checked = false; });
  updateSelectedTopics();
}
</script>
"""


@app.route("/exams")
@login_required
def exams_page():
    topics = db.list_topics_with_counts()
    grouped = {}
    for t in topics:
        grouped.setdefault(t["course_dir"], []).append(t)
    exams = db.list_exams()
    return render_page(
        EXAMS_HTML,
        active_tab="exams",
        grouped_topics=grouped,
        exams=exams,
    )


@app.route("/exams/create", methods=["POST"])
@login_required
def create_exam_route():
    try:
        topic_ids = [int(x) for x in request.form.getlist("topic_ids")]
        title = request.form.get("title", "")
        q_count = int(request.form.get("question_count", 15))
        pts = float(request.form.get("points_per_question", 5.0))
        max_att = int(request.form.get("max_attempts", 1))

        exam = db.create_exam(
            title=title,
            topic_ids=topic_ids,
            question_count=q_count,
            points_per_question=pts,
            max_attempts=max_att,
        )
        flash(
            f"✅ '{exam['title']}' testi yaratildi ({len(topic_ids)} ta mavzu, {exam['question_count']} ta savol)!",
            "success",
        )
    except Exception as e:
        flash(f"❌ Test yaratishda xatolik: {e}", "danger")
    return redirect(url_for("exams_page"))


@app.route("/exams/<int:exam_id>/toggle", methods=["POST"])
@login_required
def toggle_exam_route(exam_id: int):
    db.toggle_exam_status(exam_id)
    flash("Test holati o'zgartirildi.", "info")
    return redirect(url_for("exams_page"))


@app.route("/exams/<int:exam_id>/delete", methods=["POST"])
@login_required
def delete_exam_route(exam_id: int):
    db.delete_exam(exam_id)
    flash("🗑 Test o'chirildi.", "warning")
    return redirect(url_for("exams_page"))


# =====================================================================
# 5. MAVZULAR VA SAVOLLAR BAZASI (QO'SHIMCHA SAVOL QO'SHISH)
# =====================================================================

TOPICS_HTML = """
<div class="row g-4">
  <div class="col-lg-5">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-2">➕ Mavzuga yangi savol qo'shish</h5>
      <p class="text-muted small mb-3">Qo'llanmadagi 495 ta savoldan tashqari o'zingiz ham yangi savol qo'shishingiz mumkin</p>
      <form method="post" action="{{ url_for('add_question_route') }}">
        <div class="mb-3">
          <label class="form-label fw-semibold">Mavzuni tanlang</label>
          <select name="topic_id" class="form-select" required>
            {% for t in topics %}
              <option value="{{ t.id }}">[{{ t.course_dir }}] {{ "%02d"|format(t.topic_number) }}. {{ t.title }} ({{ t.question_count }} savol)</option>
            {% endfor %}
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Savol matni</label>
          <textarea name="question_text" class="form-control" rows="2" required></textarea>
        </div>
        <div class="mb-2">
          <label class="form-label small fw-semibold">1-variant (A)</label>
          <input type="text" name="option_a" class="form-control form-control-sm" required>
        </div>
        <div class="mb-2">
          <label class="form-label small fw-semibold">2-variant (B)</label>
          <input type="text" name="option_b" class="form-control form-control-sm" required>
        </div>
        <div class="mb-2">
          <label class="form-label small fw-semibold">3-variant (C)</label>
          <input type="text" name="option_c" class="form-control form-control-sm" required>
        </div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">4-variant (D)</label>
          <input type="text" name="option_d" class="form-control form-control-sm" required>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">To'g'ri javob varianti</label>
          <select name="correct_option" class="form-select" required>
            <option value="1">1-variant (A)</option>
            <option value="2">2-variant (B)</option>
            <option value="3">3-variant (C)</option>
            <option value="4">4-variant (D)</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Izoh (ixtiyoriy)</label>
          <input type="text" name="explanation" class="form-control" placeholder="Nega bu javob to'g'riligi haqida qisqa izoh">
        </div>
        <button type="submit" class="btn btn-primary w-100 fw-semibold">Savolni bazaga qo'shish</button>
      </form>
    </div>
  </div>

  <div class="col-lg-7">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-3">📚 Qo'llanmadagi barcha mavzular ({{ topics|length }} ta)</h5>
      <div class="table-responsive" style="max-height: 620px;">
        <table class="table table-sm table-hover align-middle">
          <thead class="table-light sticky-top">
            <tr>
              <th>Kurs</th>
              <th>№</th>
              <th>Mavzu nomi</th>
              <th>Bob</th>
              <th>Savollar</th>
            </tr>
          </thead>
          <tbody>
            {% for t in topics %}
            <tr>
              <td><span class="badge bg-info-subtle text-dark">{{ t.course_dir }}</span></td>
              <td class="fw-bold">{{ "%02d"|format(t.topic_number) }}</td>
              <td>{{ t.title }}</td>
              <td class="small text-muted">{{ t.chapter }}</td>
              <td><span class="badge bg-primary">{{ t.question_count }} ta</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
"""


@app.route("/topics")
@login_required
def topics_page():
    topics = db.list_topics_with_counts()
    return render_page(TOPICS_HTML, active_tab="topics", topics=topics)


@app.route("/topics/add-question", methods=["POST"])
@login_required
def add_question_route():
    try:
        db.add_custom_question(
            topic_id=int(request.form.get("topic_id", 0)),
            question_text=request.form.get("question_text", ""),
            option_a=request.form.get("option_a", ""),
            option_b=request.form.get("option_b", ""),
            option_c=request.form.get("option_c", ""),
            option_d=request.form.get("option_d", ""),
            correct_option=int(request.form.get("correct_option", 1)),
            explanation=request.form.get("explanation", ""),
        )
        flash("✅ Yangi savol mavzuga muvaffaqiyatli qo'shildi!", "success")
    except Exception as e:
        flash(f"❌ Xatolik: {e}", "danger")
    return redirect(url_for("topics_page"))


if __name__ == "__main__":
    # Ishga tushganda avtomatik PostgreSQL jadvallarini yaratadi va 82 ta mavzu / 495 ta savolni yuklaydi
    db.seed_topics_and_questions()
    port = int(os.getenv("ADMIN_PORT", "5000"))
    print(f"🚀 O'qituvchi Admin Paneli http://localhost:{port} manzilida ishga tushdi!")
    print(f"🔑 Standart kirish: Login = {ADMIN_USERNAME} | Parol = {ADMIN_PASSWORD}")
    app.run(host="0.0.0.0", port=port, debug=True)
