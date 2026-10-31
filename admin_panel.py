#!/usr/bin/env python3
"""
admin_panel.py — O'qituvchi Admin Paneli va O'quvchilar Web Test Platformasi (Flask + PostgreSQL).

Ushbu ilova quyidagi 2 ta to'liq bo'limni o'z ichiga oladi:
  1. O'QITUVCHI ADMIN PANELI (/admin):
     - Kim qancha ball olganini real vaqtda ko'rish, filtrlash, tahlil qilish va Excel/CSV yuklab olish
     - Har bir o'quvchi uchun alohida Login va Parol yaratish/tahrirlash
     - Qaysi va nechta mavzular bo'yicha test bo'lishini, nechta savol tushishini va ballarni belgilash
     - Mavzular va savollar bazasi (82 ta mavzu, 495+ savol)

  2. O'QUVCHILAR WEB TEST PORTALI (/student):
     - O'quvchi admin bergan Login va Parol orqali tizimga kiradi
     - O'qituvchi ochgan testlarni ko'radi va brauzerning o'zida interaktiv ishlaydi
     - Test yakunida to'plagan bali, foizi, bahosi (5, 4, 3, 2) va xatolar tahlilini ko'radi
     - Shaxsiy profilida F.I.Sh va loginini ko'rib, faqat o'z PAROLINI o'zgartira oladi
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
    jsonify,
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


# =====================================================================
# AUTH DEKORATORLARI
# =====================================================================

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)

    return wrapper


def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("student_id"):
            return redirect(url_for("student_login"))
        return fn(*args, **kwargs)

    return wrapper


def grade_badge_html(percentage: float) -> str:
    if percentage >= 86:
        return f'<span class="badge bg-success">{percentage}% (5 - A\'lo)</span>'
    elif percentage >= 71:
        return f'<span class="badge bg-primary">{percentage}% (4 - Yaxshi)</span>'
    elif percentage >= 55:
        return f'<span class="badge bg-warning text-dark">{percentage}% (3 - Qoniqarli)</span>'
    else:
        return f'<span class="badge bg-danger">{percentage}% (2 - Qoniqarsiz)</span>'


# =====================================================================
# BAZAVIY HTML SHABLON
# =====================================================================

BASE_LAYOUT = """
<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title or "web_fullstak — Test Tizimi" }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    body { background-color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif; color: #1e293b; min-height: 100vh; display: flex; flex-direction: column; }
    .navbar-admin { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
    .navbar-student { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); }
    .stat-card { border: none; border-radius: 14px; box-shadow: 0 4px 14px rgba(15,23,42,0.06); }
    .content-card { border: none; border-radius: 14px; box-shadow: 0 4px 18px rgba(15,23,42,0.05); background: #fff; }
    .topic-box { max-height: 420px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
    code.cred { background: #eef2ff; color: #3730a3; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 0.9em; }
    .q-nav-btn { width: 38px; height: 38px; font-weight: 600; padding: 0; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; margin: 3px; font-size: 0.88rem; }
    .opt-label { display: block; padding: 14px 18px; border: 2px solid #e2e8f0; border-radius: 12px; cursor: pointer; transition: all 0.2s ease; background: #fff; font-size: 1rem; }
    .opt-label:hover { border-color: #6366f1; background: #f8fafc; }
    .opt-input:checked + .opt-label { border-color: #4f46e5; background: #eef2ff; font-weight: 600; box-shadow: 0 0 0 1px #4f46e5; }
    footer { margin-top: auto; }
  </style>
</head>
<body>

{% if session.get('is_admin') %}
  <!-- O'QITUVCHI NAVBAR -->
  <nav class="navbar navbar-expand-lg navbar-dark navbar-admin mb-4 py-3 shadow-sm">
    <div class="container">
      <a class="navbar-brand fw-bold d-flex align-items-center gap-2" href="{{ url_for('admin_dashboard') }}">
        <span>🎓 web_fullstak</span> <span class="badge bg-primary text-uppercase" style="font-size:0.65rem;">O'qituvchi</span>
      </a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navMenu">
        <ul class="navbar-nav me-auto mb-2 mb-lg-0 ms-lg-4 gap-1">
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'results' %}active fw-semibold text-white{% endif %}" href="{{ url_for('admin_dashboard') }}">
              📊 Natijalar va Ballar
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'students' %}active fw-semibold text-white{% endif %}" href="{{ url_for('students_page') }}">
              👨‍🎓 O'quvchilar (Login / Parol)
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'exams' %}active fw-semibold text-white{% endif %}" href="{{ url_for('exams_page') }}">
              📝 Testlar va Mavzular
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'topics' %}active fw-semibold text-white{% endif %}" href="{{ url_for('topics_page') }}">
              📚 Savollar bazasi ({{ stats.questions_count if stats else '' }})
            </a>
          </li>
        </ul>
        <div class="d-flex gap-2">
          <form method="post" action="{{ url_for('sync_html_route') }}" class="m-0">
            <button type="submit" class="btn btn-outline-light btn-sm">🔄 Sinxronlash</button>
          </form>
          <a href="{{ url_for('admin_logout') }}" class="btn btn-danger btn-sm">Chiqish</a>
        </div>
      </div>
    </div>
  </nav>

{% elif session.get('student_id') %}
  <!-- O'QUVCHI NAVBAR -->
  <nav class="navbar navbar-expand-lg navbar-dark navbar-student mb-4 py-3 shadow-sm">
    <div class="container">
      <a class="navbar-brand fw-bold d-flex align-items-center gap-2" href="{{ url_for('student_exams_page') }}">
        <span>💻 web_fullstak</span> <span class="badge bg-indigo text-uppercase" style="background:#4338ca; font-size:0.65rem;">O'quvchi</span>
      </a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navStudentMenu">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navStudentMenu">
        <ul class="navbar-nav me-auto mb-2 mb-lg-0 ms-lg-3 gap-1">
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'student_exams' %}active fw-semibold text-white{% endif %}" href="{{ url_for('student_exams_page') }}">
              📝 Testlar ro'yxati
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'student_results' %}active fw-semibold text-white{% endif %}" href="{{ url_for('student_my_results') }}">
              📊 Mening natijalarim
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link {% if active_tab == 'student_profile' %}active fw-semibold text-white{% endif %}" href="{{ url_for('student_profile_page') }}">
              👤 Profilim va Parol
            </a>
          </li>
        </ul>
        <div class="d-flex align-items-center gap-3">
          <span class="text-light small d-none d-md-inline">
            👨‍🎓 <b>{{ session.get('student_name') }}</b> ({{ session.get('student_class') }})
          </span>
          <a href="{{ url_for('student_logout') }}" class="btn btn-outline-light btn-sm">Chiqish</a>
        </div>
      </div>
    </div>
  </nav>

{% else %}
  <!-- MEHMON NAVBAR -->
  <nav class="navbar navbar-dark bg-dark mb-4 py-3 shadow-sm">
    <div class="container d-flex justify-content-between">
      <a class="navbar-brand fw-bold" href="{{ url_for('home') }}">
        🎓 web_fullstak — Test Tizimi
      </a>
      <div class="d-flex gap-2">
        <a href="{{ url_for('student_login') }}" class="btn btn-primary btn-sm fw-semibold">👨‍🎓 O'quvchi kirish</a>
        <a href="{{ url_for('admin_login') }}" class="btn btn-outline-light btn-sm">🔐 O'qituvchi</a>
      </div>
    </div>
  </nav>
{% endif %}

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

<footer class="py-3 text-center text-muted small bg-white border-top">
  web_fullstak — 8-sinf va Full-Stack dasturlash test tizimi • PostgreSQL & Flask
</footer>

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
# ASOSIY PORTAL (LANDING PAGE)
# =====================================================================

HOME_HTML = """
<div class="row justify-content-center my-5">
  <div class="col-lg-9">
    <div class="card content-card p-5 text-center shadow">
      <h1 class="fw-bold mb-3">🎓 web_fullstak Test Tizimiga Xush Kelibsiz!</h1>
      <p class="lead text-muted mb-4">
        8-sinf «Web Full-stack dasturlash», «Computer Science Foundation» va Full-stack qo'llanmasi
        bo'yicha interaktiv test platformasi.
      </p>

      <div class="row g-4 justify-content-center mt-2">
        <div class="col-md-5">
          <div class="card h-100 p-4 border-2 border-primary-subtle rounded-4 text-start bg-primary-subtle bg-opacity-10">
            <div class="fs-1 mb-2">👨‍🎓</div>
            <h4 class="fw-bold text-primary">O'quvchilar uchun</h4>
            <p class="text-muted small">
              O'qituvchi bergan login va parolingiz orqali kiring, testlarni yeching, ballaringizni ko'ring va xatolaringizni tahlil qiling.
            </p>
            <a href="{{ url_for('student_login') }}" class="btn btn-primary w-100 fw-semibold py-2 mt-auto">
              O'quvchi kabinetiga kirish →
            </a>
          </div>
        </div>

        <div class="col-md-5">
          <div class="card h-100 p-4 border-2 border-dark-subtle rounded-4 text-start bg-light">
            <div class="fs-1 mb-2">🔐</div>
            <h4 class="fw-bold text-dark">O'qituvchilar uchun</h4>
            <p class="text-muted small">
              O'quvchilarga shaxsiy login-parol berish, qaysi mavzular bo'yicha nechta savoldan test bo'lishini sozlash va natijalarni kuzatish.
            </p>
            <a href="{{ url_for('admin_login') }}" class="btn btn-dark w-100 fw-semibold py-2 mt-auto">
              O'qituvchi Admin Paneli →
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
"""


@app.route("/")
def home():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if session.get("student_id"):
        return redirect(url_for("student_exams_page"))
    return render_page(HOME_HTML, page_title="web_fullstak — Test Tizimi")


# =====================================================================
# 1. O'QUVCHI BO'LIMI (WEB TEST ENGINE, PROFIL, PAROL O'ZGARTIRISH)
# =====================================================================

STUDENT_LOGIN_HTML = """
<div class="row justify-content-center my-5">
  <div class="col-md-5 col-lg-4">
    <div class="card content-card p-4">
      <div class="text-center mb-3">
        <div class="fs-1">👨‍🎓</div>
        <h4 class="fw-bold mb-1">O'quvchi kabineti</h4>
        <p class="text-muted small">O'qituvchi bergan login va parolingizni kiriting</p>
      </div>
      <form method="post">
        <div class="mb-3">
          <label class="form-label fw-semibold">Login</label>
          <input type="text" name="login" class="form-control" required autofocus placeholder="Masalan: aliyev_vali">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Parol</label>
          <input type="password" name="password" class="form-control" required placeholder="••••••••">
        </div>
        <button type="submit" class="btn btn-primary w-100 fw-semibold py-2">Tizimga kirish</button>
      </form>
    </div>
  </div>
</div>
"""


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if session.get("student_id"):
        return redirect(url_for("student_exams_page"))

    if request.method == "POST":
        login_val = request.form.get("login", "")
        password_val = request.form.get("password", "")
        res = db.authenticate_student_web(login_val, password_val)
        if res["ok"]:
            st = res["student"]
            session["student_id"] = st["id"]
            session["student_name"] = st["full_name"]
            session["student_class"] = st["class_name"]
            session["student_login"] = st["login"]
            flash(f"Xush kelibsiz, {st['full_name']}!", "success")
            return redirect(url_for("student_exams_page"))
        flash(res["error"], "danger")

    return render_page(STUDENT_LOGIN_HTML, page_title="O'quvchi kirish")


@app.route("/student/logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_name", None)
    session.pop("student_class", None)
    session.pop("student_login", None)
    flash("Tizimdan chiqdingiz.", "info")
    return redirect(url_for("student_login"))


STUDENT_EXAMS_HTML = """
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h4 class="fw-bold mb-1">📝 Mavjud testlar</h4>
    <p class="text-muted small mb-0">O'qituvchingiz tomonidan belgilangan mavzular bo'yicha testlar</p>
  </div>
  <a href="{{ url_for('student_my_results') }}" class="btn btn-outline-primary btn-sm">
    📊 Mening natijalarim
  </a>
</div>

<div class="row g-4">
  {% for ex in exams %}
    <div class="col-md-6">
      <div class="card content-card h-100 p-4 border-top border-4 border-primary">
        <h5 class="fw-bold mb-2">{{ ex.title }}</h5>
        <div class="small text-muted mb-3">
          <div>📚 <b>Kiritilgan mavzular ({{ ex.topic_count }} ta):</b></div>
          <div class="text-dark mt-1">{{ ex.topic_titles }}</div>
        </div>

        <div class="row g-2 mb-3 py-2 border-top border-bottom small">
          <div class="col-6">❓ Savollar: <b>{{ ex.question_count }} ta</b></div>
          <div class="col-6">🏆 Maksimal ball: <b>{{ (ex.question_count * ex.points_per_question)|round(1) }} ball</b></div>
          <div class="col-6">🔄 Urinishlar: <b>{{ ex.used_attempts }} / {{ ex.max_attempts }}</b></div>
          <div class="col-6">👥 Guruh: <b>{{ ex.target_groups }}</b></div>
          <div class="col-12 mt-1">
            {% if ex.best_score is not none %}
              ⭐️ Eng yaxshi: <b class="text-success">{{ ex.best_score }} ball</b>
            {% else %}
              ⭐️ Holat: <span class="text-muted">Topshirilmagan</span>
            {% endif %}
          </div>
        </div>

        <div class="mt-auto">
          {% if ex.used_attempts < ex.max_attempts %}
            <a href="{{ url_for('student_start_exam', exam_id=ex.id) }}" class="btn btn-primary w-100 fw-semibold">
              ▶️ Testni boshlash
            </a>
          {% else %}
            <button class="btn btn-secondary w-100" disabled>
              ✅ Barcha urinishlardan foydalanilgan
            </button>
          {% endif %}
        </div>
      </div>
    </div>
  {% else %}
    <div class="col-12">
      <div class="card content-card p-5 text-center text-muted">
        <div class="fs-1 mb-2">📭</div>
        <h5>Hozirda faol testlar yo'q</h5>
        <p class="small mb-0">O'qituvchi yangi test e'lon qilganda shu yerda paydo bo'ladi.</p>
      </div>
    </div>
  {% endfor %}
</div>
"""


@app.route("/student/exams")
@student_required
def student_exams_page():
    student_id = session["student_id"]
    exams = db.get_active_exams_for_student(student_id)
    return render_page(
        STUDENT_EXAMS_HTML,
        active_tab="student_exams",
        exams=exams,
        page_title="Mavjud testlar — O'quvchi",
    )


@app.route("/student/exam/<int:exam_id>/start")
@student_required
def student_start_exam(exam_id: int):
    student_id = session["student_id"]
    res = db.start_or_resume_attempt(student_id, exam_id)
    if not res["ok"]:
        flash(res["error"], "warning")
        return redirect(url_for("student_exams_page"))

    attempt_id = res["attempt"]["id"]
    return redirect(url_for("student_attempt_page", attempt_id=attempt_id))


STUDENT_ATTEMPT_HTML = """
<div class="row justify-content-center">
  <div class="col-lg-10">
    <div class="card content-card p-4 mb-4">
      <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
        <div>
          <h5 class="fw-bold mb-1">{{ attempt.exam_title }}</h5>
          <small class="text-muted">
            Jami savollar: {{ attempt.total_questions }} ta •
            Javob berildi: <b>{{ attempt.answered_count }}</b> / {{ attempt.total_questions }}
          </small>
        </div>
        <div>
          <button type="button" class="btn btn-danger btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#finishModal">
            🏁 Testni yakunlash
          </button>
        </div>
      </div>

      <!-- Savollar navigatsiya tugmalari -->
      <div class="d-flex flex-wrap mt-3 pt-3 border-top">
        {% for q in attempt.questions %}
          {% set is_curr = (q.question_order == current_order) %}
          {% set is_ans = (q.selected_option is not none) %}
          <a href="{{ url_for('student_attempt_page', attempt_id=attempt.id, q=q.question_order) }}"
             class="btn q-nav-btn {% if is_curr %}btn-primary{% elif is_ans %}btn-success{% else %}btn-outline-secondary{% endif %}">
            {{ q.question_order }}
          </a>
        {% endfor %}
      </div>
    </div>

    <!-- Hozirgi savol kartasi -->
    {% if current_q %}
    <div class="card content-card p-4 mb-4">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <span class="badge bg-primary px-3 py-2">
          {{ current_q.question_order }} / {{ attempt.total_questions }} - savol
        </span>
        <span class="badge bg-secondary-subtle text-dark">
          📘 {{ current_q.topic_title }}
        </span>
      </div>

      <h5 class="fw-bold mb-4" style="line-height: 1.5;">{{ current_q.question_text }}</h5>

      <form method="post" action="{{ url_for('student_submit_answer', attempt_id=attempt.id) }}">
        <input type="hidden" name="question_order" value="{{ current_q.question_order }}">

        <div class="mb-3">
          {% for opt_num, opt_text in [
            (1, current_q.option_a),
            (2, current_q.option_b),
            (3, current_q.option_c),
            (4, current_q.option_d)
          ] %}
            <div class="mb-2">
              <input type="radio" class="d-none opt-input" name="selected_option" id="opt_{{ opt_num }}"
                     value="{{ opt_num }}" {% if current_q.selected_option == opt_num %}checked{% endif %}
                     onchange="this.form.submit()">
              <label class="opt-label" for="opt_{{ opt_num }}">
                <span class="badge bg-light text-dark border me-2">{{ ['A', 'B', 'C', 'D'][opt_num-1] }}</span>
                {{ opt_text }}
              </label>
            </div>
          {% endfor %}
        </div>

        <div class="d-flex justify-content-between align-items-center pt-2">
          {% if current_order > 1 %}
            <a href="{{ url_for('student_attempt_page', attempt_id=attempt.id, q=current_order-1) }}"
               class="btn btn-outline-secondary">← Oldingi savol</a>
          {% else %}
            <div></div>
          {% endif %}

          <button type="submit" class="btn btn-primary fw-semibold">
            Saqlash va keyingisi →
          </button>
        </div>
      </form>
    </div>
    {% endif %}

  </div>
</div>

<!-- Testni yakunlash Modal -->
<div class="modal fade" id="finishModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title fw-bold">Testni yakunlaysizmi?</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <p>
          Siz <b>{{ attempt.total_questions }} ta</b> savoldan <b>{{ attempt.answered_count }} tasiga</b> javob berdingiz.
        </p>
        {% if attempt.answered_count < attempt.total_questions %}
          <div class="alert alert-warning small">
            ⚠️ Diqqat: Siz barcha savollarga javob bermadingiz. Javob berilmagan savollar xato deb hisoblanadi!
          </div>
        {% endif %}
        <p class="mb-0">Test yakunlangach natijangiz va to'plagan balingiz hisoblanadi.</p>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Ortga</button>
        <form method="post" action="{{ url_for('student_finish_attempt', attempt_id=attempt.id) }}">
          <button type="submit" class="btn btn-danger fw-semibold">Ha, testni yakunlash</button>
        </form>
      </div>
    </div>
  </div>
</div>
"""


@app.route("/student/attempt/<int:attempt_id>")
@student_required
def student_attempt_page(attempt_id: int):
    attempt = db.get_attempt_for_web(attempt_id)
    if not attempt or attempt["student_id"] != session["student_id"]:
        flash("Test urinishi topilmadi.", "danger")
        return redirect(url_for("student_exams_page"))

    if attempt["status"] == "completed":
        return redirect(url_for("student_attempt_result", attempt_id=attempt_id))

    q_order = request.args.get("q")
    if q_order and q_order.isdigit():
        current_order = int(q_order)
    else:
        # Birinchi javob berilmagan savolni topamiz
        unanswered = [q for q in attempt["questions"] if q["selected_option"] is None]
        current_order = unanswered[0]["question_order"] if unanswered else 1

    current_q = next((q for q in attempt["questions"] if q["question_order"] == current_order), None)
    if not current_q and attempt["questions"]:
        current_q = attempt["questions"][0]
        current_order = current_q["question_order"]

    return render_page(
        STUDENT_ATTEMPT_HTML,
        attempt=attempt,
        current_q=current_q,
        current_order=current_order,
        page_title=f"{attempt['exam_title']} — Test",
    )


@app.route("/student/attempt/<int:attempt_id>/submit", methods=["POST"])
@student_required
def student_submit_answer(attempt_id: int):
    q_order = int(request.form.get("question_order", 1))
    sel_opt = request.form.get("selected_option")

    if sel_opt and sel_opt.isdigit():
        db.submit_question_answer(attempt_id, q_order, int(sel_opt))

    attempt = db.get_attempt_for_web(attempt_id)
    if not attempt or attempt["status"] == "completed":
        return redirect(url_for("student_attempt_result", attempt_id=attempt_id))

    # Navbatdagi savolga o'tamiz
    next_order = q_order + 1
    if next_order > attempt["total_questions"]:
        # Agar oxirgi savol bo'lsa, birinchi javob berilmagan savolga o'tamiz
        unanswered = [q for q in attempt["questions"] if q["selected_option"] is None]
        if unanswered:
            next_order = unanswered[0]["question_order"]
        else:
            # Barchasi yechildi — avtomatik yakunlash
            db.finish_attempt_force(attempt_id)
            return redirect(url_for("student_attempt_result", attempt_id=attempt_id))

    return redirect(url_for("student_attempt_page", attempt_id=attempt_id, q=next_order))


@app.route("/student/attempt/<int:attempt_id>/finish", methods=["POST"])
@student_required
def student_finish_attempt(attempt_id: int):
    db.finish_attempt_force(attempt_id)
    return redirect(url_for("student_attempt_result", attempt_id=attempt_id))


STUDENT_RESULT_HTML = """
<div class="row justify-content-center">
  <div class="col-lg-7">
    <div class="card content-card p-5 text-center mb-4">
      <div class="fs-1 mb-2">🎉</div>
      <h3 class="fw-bold mb-1">Test yakunlandi!</h3>
      <p class="text-muted">{{ attempt.exam_title }}</p>

      <div class="row g-3 my-3">
        <div class="col-md-4">
          <div class="p-3 bg-light rounded-3">
            <div class="text-muted small">To'g'ri javoblar</div>
            <div class="fs-3 fw-bold text-success">{{ attempt.correct_answers }} / {{ attempt.total_questions }} ta</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="p-3 bg-light rounded-3">
            <div class="text-muted small">To'plangan ball</div>
            <div class="fs-3 fw-bold text-primary">{{ attempt.score_points }} / {{ attempt.max_points }}</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="p-3 bg-light rounded-3">
            <div class="text-muted small">Foiz / Baho</div>
            <div class="fs-4 fw-bold mt-1">
              {% if attempt.percentage >= 86 %}
                <span class="badge bg-success">{{ attempt.percentage }}% (5)</span>
              {% elif attempt.percentage >= 71 %}
                <span class="badge bg-primary">{{ attempt.percentage }}% (4)</span>
              {% elif attempt.percentage >= 55 %}
                <span class="badge bg-warning text-dark">{{ attempt.percentage }}% (3)</span>
              {% else %}
                <span class="badge bg-danger">{{ attempt.percentage }}% (2)</span>
              {% endif %}
            </div>
          </div>
        </div>
      </div>

      <p class="small text-muted mb-4">
        Sizning natijangiz o'qituvchi Admin Paneliga avtomatik yuborildi va qayd etildi.
      </p>

      <div class="d-flex justify-content-center gap-2">
        <a href="{{ url_for('student_attempt_review', attempt_id=attempt.id) }}" class="btn btn-outline-primary fw-semibold">
          🔍 Xatolar va to'g'ri javoblarni ko'rish
        </a>
        <a href="{{ url_for('student_exams_page') }}" class="btn btn-primary fw-semibold">
          Boshqa testlar →
        </a>
      </div>
    </div>
  </div>
</div>
"""


@app.route("/student/attempt/<int:attempt_id>/result")
@student_required
def student_attempt_result(attempt_id: int):
    attempt = db.get_attempt_for_web(attempt_id)
    if not attempt or attempt["student_id"] != session["student_id"]:
        flash("Natija topilmadi.", "danger")
        return redirect(url_for("student_exams_page"))
    return render_page(STUDENT_RESULT_HTML, attempt=attempt, page_title="Test natijasi")


STUDENT_REVIEW_HTML = """
<div class="mb-3 d-flex justify-content-between align-items-center">
  <a href="{{ url_for('student_my_results') }}" class="btn btn-outline-secondary btn-sm">
    ← Natijalarimga qaytish
  </a>
  <span class="fw-bold">{{ detail.exam_title }} — Javoblar tahlili</span>
</div>

<div class="card content-card p-4">
  <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom">
    <div>
      <h5 class="fw-bold mb-1">To'plangan ball: {{ detail.score_points }} / {{ detail.max_points }} ball</h5>
      <span class="text-muted small">To'g'ri javoblar: {{ detail.correct_answers }} / {{ detail.total_questions }} ta ({{ detail.percentage }}%)</span>
    </div>
    <a href="{{ url_for('student_exams_page') }}" class="btn btn-primary btn-sm">Boshqa testlar</a>
  </div>

  {% for a in detail.answers %}
    <div class="border rounded-3 p-3 mb-3 {% if a.is_correct %}border-success bg-success-subtle{% else %}border-danger bg-danger-subtle{% endif %} bg-opacity-10">
      <div class="d-flex justify-content-between mb-2">
        <span class="fw-bold">{{ a.question_order }}-savol. {{ a.question_text }}</span>
        <span class="badge bg-dark">{{ a.topic_title }}</span>
      </div>
      <ol class="mb-2">
        {% for opt in [a.option_a, a.option_b, a.option_c, a.option_d] %}
          <li class="{% if loop.index == a.correct_option %}fw-bold text-success{% elif loop.index == a.selected_option and not a.is_correct %}fw-bold text-danger text-decoration-line-through{% endif %}">
            {{ opt }}
            {% if loop.index == a.correct_option %} ✅ (To'g'ri javob){% endif %}
            {% if loop.index == a.selected_option and not a.is_correct %} ❌ (Sizning javobingiz){% endif %}
          </li>
        {% endfor %}
      </ol>
      {% if a.explanation %}
        <div class="small text-muted mt-2 pt-2 border-top">💡 <i>{{ a.explanation }}</i></div>
      {% endif %}
    </div>
  {% endfor %}
</div>
"""


@app.route("/student/attempt/<int:attempt_id>/review")
@student_required
def student_attempt_review(attempt_id: int):
    detail = db.get_attempt_detail(attempt_id)
    if not detail or detail["student_id"] != session["student_id"]:
        flash("Tahlil topilmadi.", "danger")
        return redirect(url_for("student_exams_page"))
    return render_page(STUDENT_REVIEW_HTML, detail=detail, page_title="Savollar tahlili")


STUDENT_MY_RESULTS_HTML = """
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h4 class="fw-bold mb-1">📊 Mening natijalarim</h4>
    <p class="text-muted small mb-0">Siz topshirgan testlar va to'plagan ballaringiz tarixi</p>
  </div>
  <a href="{{ url_for('student_exams_page') }}" class="btn btn-primary btn-sm">📝 Yangi test ishlash</a>
</div>

<div class="card content-card p-4">
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0">
      <thead class="table-light">
        <tr>
          <th>#</th>
          <th>Test nomi</th>
          <th>To'g'ri javob</th>
          <th>To'plangan ball</th>
          <th>Foiz / Baho</th>
          <th>Topshirilgan vaqt</th>
          <th>Amal</th>
        </tr>
      </thead>
      <tbody>
        {% for a in attempts %}
        <tr>
          <td>{{ loop.index }}</td>
          <td class="fw-semibold">{{ a.exam_title }}</td>
          <td><b>{{ a.correct_answers }}</b> / {{ a.total_questions }}</td>
          <td>
            <span class="fs-6 fw-bold text-primary">{{ a.score_points }}</span>
            <small class="text-muted">/ {{ a.max_points }} ball</small>
          </td>
          <td>
            {% if a.percentage >= 86 %}
              <span class="badge bg-success">{{ a.percentage }}% (5 - A'lo)</span>
            {% elif a.percentage >= 71 %}
              <span class="badge bg-primary">{{ a.percentage }}% (4 - Yaxshi)</span>
            {% elif a.percentage >= 55 %}
              <span class="badge bg-warning text-dark">{{ a.percentage }}% (3 - Qoniqarli)</span>
            {% else %}
              <span class="badge bg-danger">{{ a.percentage }}% (2 - Qoniqarsiz)</span>
            {% endif %}
          </td>
          <td class="small text-muted">{{ a.finished_at.strftime('%d.%m.%Y %H:%M') if a.finished_at else '' }}</td>
          <td>
            <a href="{{ url_for('student_attempt_review', attempt_id=a.id) }}" class="btn btn-outline-primary btn-sm">
              🔍 Tahlil
            </a>
          </td>
        </tr>
        {% else %}
        <tr>
          <td colspan="7" class="text-center text-muted py-4">
            Siz hali birorta ham test topshirmagansiz. «Yangi test ishlash» tugmasi orqali testni boshlang.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""


@app.route("/student/my-results")
@student_required
def student_my_results():
    student_id = session["student_id"]
    attempts = db.list_student_attempts(student_id)
    return render_page(
        STUDENT_MY_RESULTS_HTML,
        active_tab="student_results",
        attempts=attempts,
        page_title="Mening natijalarim",
    )


STUDENT_PROFILE_HTML = """
<div class="row justify-content-center">
  <div class="col-lg-7">
    <div class="card content-card p-4 mb-4">
      <h5 class="fw-bold mb-3">👤 Shaxsiy profilingiz</h5>
      <p class="text-muted small">
        Sizning ma'lumotlaringiz o'qituvchi tomonidan kiritilgan. Siz faqat parolingizni o'zgartira olasiz.
      </p>

      <div class="row g-3 py-2 border-top border-bottom mb-4">
        <div class="col-sm-6">
          <small class="text-muted d-block">F.I.Sh</small>
          <span class="fw-bold fs-6">{{ student.full_name }}</span>
        </div>
        <div class="col-sm-6">
          <small class="text-muted d-block">Sinf / Guruh</small>
          <span class="badge bg-secondary fs-6">{{ student.class_name }}</span>
        </div>
        <div class="col-sm-6">
          <small class="text-muted d-block">Login (o'zgarmas)</small>
          <code class="cred fs-6">{{ student.login }}</code>
        </div>
        <div class="col-sm-6">
          <small class="text-muted d-block">Telegram holati</small>
          {% if student.telegram_id %}
            <span class="badge bg-success-subtle text-success">✅ Ulangan</span>
          {% else %}
            <span class="badge bg-light text-muted border">Ulanmagan</span>
          {% endif %}
        </div>
      </div>

      <!-- PAROLNI O'ZGARTIRISH FORMASI -->
      <h5 class="fw-bold mb-2">🔑 Parolni o'zgartirish</h5>
      <p class="text-muted small mb-3">Xavfsizligingiz uchun o'zingiz eslab qoladigan yangi parol o'rnating</p>

      <form method="post" action="{{ url_for('student_change_password') }}">
        <div class="mb-3">
          <label class="form-label fw-semibold">Joriy (eski) parol</label>
          <input type="password" name="old_password" class="form-control" required placeholder="Hozirgi parolingiz">
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <label class="form-label fw-semibold">Yangi parol</label>
            <input type="password" name="new_password" class="form-control" required placeholder="Kamida 4 ta belgi">
          </div>
          <div class="col-md-6">
            <label class="form-label fw-semibold">Yangi parolni takrorlang</label>
            <input type="password" name="confirm_password" class="form-control" required placeholder="Yangi parolni qayta kiriting">
          </div>
        </div>
        <button type="submit" class="btn btn-primary fw-semibold">
          🔒 Parolni yangilash
        </button>
      </form>
    </div>
  </div>
</div>
"""


@app.route("/student/profile")
@student_required
def student_profile_page():
    student = db.get_student_by_id(session["student_id"])
    if not student:
        return redirect(url_for("student_logout"))
    return render_page(
        STUDENT_PROFILE_HTML,
        active_tab="student_profile",
        student=student,
        page_title="Profilim va Parol",
    )


@app.route("/student/profile/change-password", methods=["POST"])
@student_required
def student_change_password():
    student_id = session["student_id"]
    old_p = request.form.get("old_password", "")
    new_p = request.form.get("new_password", "")
    conf_p = request.form.get("confirm_password", "")

    if new_p != conf_p:
        flash("❌ Yangi parol va tasdiqlash paroli bir-biriga mos kelmadi!", "danger")
        return redirect(url_for("student_profile_page"))

    res = db.change_student_password(student_id, old_p, new_p)
    if res["ok"]:
        flash("✅ Parolingiz muvaffaqiyatli o'zgartirildi! Keyingi safar yangi parol bilan kiring.", "success")
    else:
        flash(f"❌ {res['error']}", "danger")

    return redirect(url_for("student_profile_page"))


# =====================================================================
# 2. O'QITUVCHI ADMIN PANELI BO'LIMI
# =====================================================================

ADMIN_LOGIN_HTML = """
<div class="row justify-content-center my-5">
  <div class="col-md-5 col-lg-4">
    <div class="card content-card p-4">
      <div class="text-center mb-3">
        <div class="fs-1">🔐</div>
        <h4 class="fw-bold mb-1">O'qituvchi kabineti</h4>
        <p class="text-muted small">Testlar, mavzular va o'quvchilar ballarini boshqarish</p>
      </div>
      <form method="post">
        <div class="mb-3">
          <label class="form-label fw-semibold">Admin login</label>
          <input type="text" name="username" class="form-control" required autofocus placeholder="admin">
        </div>
        <div class="mb-3">
          <label class="form-label fw-semibold">Admin parol</label>
          <input type="password" name="password" class="form-control" required placeholder="••••••••">
        </div>
        <button type="submit" class="btn btn-dark w-100 fw-semibold py-2">Tizimga kirish</button>
      </form>
    </div>
  </div>
</div>
"""


@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Xush kelibsiz! O'qituvchi paneliga kirdingiz.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Login yoki parol noto'g'ri!", "danger")

    return render_page(ADMIN_LOGIN_HTML, page_title="O'qituvchi kirish")


@app.route("/admin/logout")
@app.route("/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin tizimidan chiqdingiz.", "info")
    return redirect(url_for("admin_login"))


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
      <small class="text-muted">Web va Telegram bot orqali ishlangan barcha natijalar bir joyda</small>
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
      <a href="{{ url_for('admin_dashboard') }}" class="btn btn-outline-secondary btn-sm">Tozalash</a>
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
            Hozircha test natijalari yo'q. O'quvchilar Web yoki Telegram bot orqali test ishlashi bilan shu yerda ko'rinadi.
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""


@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
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


@app.route("/admin/results/export")
@admin_required
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
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "T/r", "O'quvchi F.I.Sh", "Sinf", "Login", "Test nomi",
        "To'g'ri javoblar", "Jami savollar", "To'plagan bali", "Maksimal ball",
        "Foiz (%)", "Holati", "Topshirgan vaqti",
    ])
    for idx, r in enumerate(results, 1):
        writer.writerow([
            idx, r["full_name"], r["class_name"], r["login"], r["exam_title"],
            r["correct_answers"], r["total_questions"], r["score_points"],
            r["max_points"], r["percentage"], r["status"],
            r["finished_at"].strftime("%Y-%m-%d %H:%M") if r["finished_at"] else "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=test_natijalari.csv"},
    )


ATTEMPT_DETAIL_HTML = """
<div class="mb-3">
  <a href="{{ url_for('admin_dashboard') }}" class="btn btn-outline-secondary btn-sm">← Natijalarga qaytish</a>
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


@app.route("/admin/results/<int:attempt_id>")
@admin_required
def attempt_detail_page(attempt_id: int):
    detail = db.get_attempt_detail(attempt_id)
    if not detail:
        flash("Natija topilmadi.", "warning")
        return redirect(url_for("admin_dashboard"))
    return render_page(ATTEMPT_DETAIL_HTML, active_tab="results", detail=detail)


STUDENTS_HTML = """
<div class="row g-4">
  <div class="col-lg-5">
    <div class="card content-card p-4">
      <ul class="nav nav-pills nav-fill mb-3" id="studentAddTabs" role="tablist">
        <li class="nav-item" role="presentation">
          <button class="nav-link active fw-semibold py-2" id="bulk-tab" data-bs-toggle="pill" data-bs-target="#bulkPane" type="button" role="tab">
            📋 Ommaviy yuklash
          </button>
        </li>
        <li class="nav-item" role="presentation">
          <button class="nav-link fw-semibold py-2" id="single-tab" data-bs-toggle="pill" data-bs-target="#singlePane" type="button" role="tab">
            ➕ Bittalab qo'shish
          </button>
        </li>
      </ul>

      <div class="tab-content" id="studentAddContent">
        <!-- 1. OMMAVIY YUKLASH (RO'YXAT BO'YICHA) -->
        <div class="tab-pane fade show active" id="bulkPane" role="tabpanel">
          <h6 class="fw-bold mb-1">Guruh ro'yxatini yuklash</h6>
          <p class="text-muted small mb-2">
            O'quvchilar ma'lumotlarini qatorma-qator nusxalab joylang.
          </p>

          <form method="post" action="{{ url_for('bulk_import_students_route') }}">
            <div class="mb-2">
              <label class="form-label small fw-semibold">Ro'yxat (Guruh, F.I.Sh, [Login], [Parol])</label>
              <textarea name="bulk_text" class="form-control font-monospace" rows="9" required
                placeholder="8-A, Aliyev Vali, aliyev_v, 123456&#10;8-A, Karimov Sardor, karimov_s, pass789&#10;8-B, Umarova Madina, umarova_m, pass2026&#10;8-B, Toirov Jasur"></textarea>
            </div>

            <div class="alert alert-info py-2 px-3 small mb-3" style="font-size:0.78rem;">
              💡 <b>Format:</b> <code>Guruh, F.I.Sh, [Login], [Parol]</code><br>
              • Vergul, nuqta-vergul yoki Tab bilan 10–50 talab o'quvchini bittada kiriting.<br>
              • Agar Login yoki Parol kiritilmasa, tizim o'zi avtomatik generatsiya qiladi.
            </div>

            <button type="submit" class="btn btn-success w-100 fw-semibold py-2">
              📥 Barcha o'quvchilarni bazaga yuklash
            </button>
          </form>
        </div>

        <!-- 2. BITTALAB QO'SHISH -->
        <div class="tab-pane fade" id="singlePane" role="tabpanel">
          <h6 class="fw-bold mb-1">Yakka o'quvchi qo'shish</h6>
          <p class="text-muted small mb-2">Yagona o'quvchi uchun ma'lumot kiriting</p>

          <form method="post" action="{{ url_for('add_student_route') }}">
            <div class="mb-2">
              <label class="form-label small fw-semibold">O'quvchi F.I.Sh</label>
              <input type="text" name="full_name" class="form-control form-control-sm" required placeholder="Aliyev Vali">
            </div>
            <div class="mb-2">
              <label class="form-label small fw-semibold">Sinf yoki guruh</label>
              <input type="text" name="class_name" class="form-control form-control-sm" required value="8-A" placeholder="8-A">
            </div>
            <div class="mb-2">
              <label class="form-label small fw-semibold">Shaxsiy Login</label>
              <div class="input-group input-group-sm">
                <input type="text" id="newLogin" name="login" class="form-control" required placeholder="aliyev_v">
                <button type="button" class="btn btn-outline-secondary" onclick="genLogin()">Avto</button>
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label small fw-semibold">Boshlang'ich Parol</label>
              <div class="input-group input-group-sm">
                <input type="text" id="newPass" name="password" class="form-control" required placeholder="Parol">
                <button type="button" class="btn btn-outline-secondary" onclick="genPass()">🎲</button>
              </div>
            </div>
            <button type="submit" class="btn btn-primary w-100 fw-semibold py-2">Saqlash</button>
          </form>
        </div>
      </div>
    </div>
  </div>

  <div class="col-lg-7">
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
              <th>Joriy parol</th>
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
                  <span class="badge bg-light text-muted border">Web orqali kirgan</span>
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


@app.route("/admin/students")
@admin_required
def students_page():
    search_q = request.args.get("q", "").strip()
    students = db.list_students(search=search_q or None)
    return render_page(
        STUDENTS_HTML,
        active_tab="students",
        students=students,
        search_q=search_q,
    )



@app.route("/admin/students/bulk-import", methods=["POST"])
@admin_required
def bulk_import_students_route():
    raw_text = request.form.get("bulk_text", "")
    try:
        res = db.bulk_import_students(raw_text)
        if res["total"] > 0:
            msg = f"✅ Muvaffaqiyatli: Jami {res['added']} ta yangi o'quvchi qo'shildi! (Eski o'quvchilar o'zgartirilmasdan saqlab qolindi)"
            flash(msg, "success")
            if res.get("adjusted"):
                for adj in res["adjusted"]:
                    flash(
                        f"ℹ️ {adj['full_name']}: '{adj['original_login']}' logini oldin band bo'lgani sababli yangi login berildi: {adj['login']}",
                        "info",
                    )
        else:
            flash("⚠️ Ro'yxatdan birorta ham to'g'ri o'quvchi ma'lumoti topilmadi.", "warning")

        if res["errors"]:
            for err in res["errors"][:5]:
                flash(f"⚠️ {err}", "danger")
    except Exception as e:
        flash(f"❌ Xatolik yuz berdi: {e}", "danger")

    return redirect(url_for("students_page"))

@app.route("/admin/students/add", methods=["POST"])
@admin_required
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


@app.route("/admin/students/<int:student_id>/edit", methods=["POST"])
@admin_required
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


@app.route("/admin/students/<int:student_id>/unlink", methods=["POST"])
@admin_required
def unlink_student_route(student_id: int):
    db.unlink_student_telegram(student_id)
    flash("🔓 O'quvchining Telegram akkaunti bog'lanishdan uzildi.", "info")
    return redirect(url_for("students_page"))


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student_route(student_id: int):
    db.delete_student(student_id)
    flash("🗑 O'quvchi o'chirildi.", "warning")
    return redirect(url_for("students_page"))


EXAMS_HTML = """
<div class="row g-4">
  <div class="col-lg-6">
    <div class="card content-card p-4">
      <h5 class="fw-bold mb-1">📝 Yangi test yaratish</h5>
      <p class="text-muted small mb-3">
        Qaysi va nechta mavzular bo'yicha test bo'lishini belgilang — bot va web shu mavzulardan tasodifiy savollar tanlaydi
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

        <!-- GURUHLARNI TANLASH -->
        <div class="mb-3">
          <label class="form-label fw-semibold mb-1">
            🎯 Mo'ljallangan guruhlar (sinflar)
          </label>
          <div class="p-3 border rounded-3 bg-light">
            <div class="form-check mb-2 pb-2 border-bottom">
              <input class="form-check-input" type="checkbox" id="allGroupsCheck" name="groups" value="ALL" checked onchange="toggleAllGroups(this)">
              <label class="form-check-label fw-bold text-success" for="allGroupsCheck">
                🌐 Barcha guruhlar uchun ochiq
              </label>
            </div>
            
            {% if all_groups %}
              <div class="mb-2">
                <small class="text-muted fw-semibold d-block mb-1">Yoki aniq guruhlarni belgilang:</small>
                <div class="row g-1" id="specificGroupsBox">
                  {% for g in all_groups %}
                    <div class="col-6 col-md-4">
                      <div class="form-check">
                        <input class="form-check-input group-check" type="checkbox" name="groups" value="{{ g }}" id="grp_{{ loop.index }}" onchange="onGroupChange()">
                        <label class="form-check-label small" for="grp_{{ loop.index }}">👥 {{ g }}</label>
                      </div>
                    </div>
                  {% endfor %}
                </div>
              </div>
            {% endif %}

            <div class="mt-2 pt-2 border-top">
              <input type="text" name="custom_groups" class="form-control form-control-sm"
                     placeholder="Yangi guruhlar bo'lsa kiriting (masalan: 8-A, 8-B)">
            </div>
          </div>
          <small class="text-muted" style="font-size:0.75rem;">
            Agar aniq guruhlar tanlansa, faqat shu guruh o'quvchilari testni ko'radi va topshira oladi.
          </small>
        </div>

        <button type="submit" class="btn btn-primary w-100 fw-semibold py-2">
          ✅ Testni yaratish va belgilangan guruhlarga ochish
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
                👨‍🎓 Topshirdi: <b>{{ ex.completed_count }} kishi</b><br>
                🎯 <b>Guruhlar:</b> <span class="badge bg-primary-subtle text-primary border">{{ ex.target_groups }}</span>
              </div>
              <details class="small">
                <summary class="text-primary" style="cursor:pointer">Tanlangan mavzularni ko'rish ({{ ex.topic_count }} ta)</summary>
                <div class="mt-1 text-muted">{{ ex.topics_summary }}</div>
              </details>
            </div>
            <div class="d-flex gap-1 align-items-center">
              {% if ex.is_active %}
                <button type="button" class="btn btn-sm btn-outline-primary"
                        data-bs-toggle="modal" data-bs-target="#groupModal{{ ex.id }}"
                        title="Guruhlarni o'zgartirish">
                  🎯 Guruhlar
                </button>
                <form method="post" action="{{ url_for('toggle_exam_route', exam_id=ex.id) }}" class="m-0">
                  <input type="hidden" name="action" value="stop">
                  <button type="submit" class="btn btn-sm btn-outline-warning">
                    ⏸ To'xtatish
                  </button>
                </form>
              {% else %}
                <button type="button" class="btn btn-sm btn-success fw-semibold"
                        data-bs-toggle="modal" data-bs-target="#groupModal{{ ex.id }}">
                  ▶ Yoqish
                </button>
              {% endif %}
              <form method="post" action="{{ url_for('delete_exam_route', exam_id=ex.id) }}" class="m-0"
                    onsubmit="return confirm('Testni o\'chirishni tasdiqlaysizmi?');">
                <button type="submit" class="btn btn-outline-danger btn-sm">🗑</button>
              </form>
            </div>
          </div>

          <!-- Guruhlarni tanlab yoqish Modal -->
          <div class="modal fade" id="groupModal{{ ex.id }}" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog">
              <form method="post" action="{{ url_for('toggle_exam_route', exam_id=ex.id) }}" class="modal-content text-start">
                <input type="hidden" name="action" value="start">
                <div class="modal-header">
                  <h5 class="modal-title fw-bold">
                    {% if ex.is_active %}🎯 Guruhlarni o'zgartirish{% else %}▶ «{{ ex.title }}» testini yoqish{% endif %}
                  </h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                  <p class="text-muted small mb-3">
                    Ushbu test qaysi guruhlar (sinflar) uchun yoqilsin? Kerakli guruhlarni tanlang:
                  </p>

                  {% set is_all = (not ex.assigned_groups or ex.assigned_groups|length == 0) %}

                  <div class="p-3 border rounded-3 bg-light mb-3">
                    <div class="form-check mb-2 pb-2 border-bottom">
                      <input class="form-check-input" type="checkbox" id="modalAll_{{ ex.id }}" name="groups" value="ALL"
                             {% if is_all %}checked{% endif %} onchange="toggleModalAllGroups({{ ex.id }}, this)">
                      <label class="form-check-label fw-bold text-success" for="modalAll_{{ ex.id }}">
                        🌐 Barcha guruhlar uchun yoqish
                      </label>
                    </div>

                    {% if all_groups %}
                      <div class="mb-2">
                        <small class="text-muted fw-semibold d-block mb-2">Yoki kerakli guruhlarni tanlang:</small>
                        <div class="row g-2">
                          {% for g in all_groups %}
                            <div class="col-6">
                              <div class="form-check">
                                <input class="form-check-input modal-grp-{{ ex.id }}" type="checkbox" name="groups" value="{{ g }}"
                                       id="mgrp_{{ ex.id }}_{{ loop.index }}"
                                       {% if not is_all and g in ex.assigned_groups %}checked{% endif %}
                                       onchange="onModalGroupChange({{ ex.id }})">
                                <label class="form-check-label small" for="mgrp_{{ ex.id }}_{{ loop.index }}">
                                  👥 {{ g }}
                                </label>
                              </div>
                            </div>
                          {% endfor %}
                        </div>
                      </div>
                    {% endif %}

                    <div class="mt-2 pt-2 border-top">
                      <label class="form-label small text-muted mb-1">Yangi guruh nomi (ixtiyoriy):</label>
                      <input type="text" name="custom_groups" class="form-control form-control-sm"
                             placeholder="Masalan: 8-A, 8-B (vergul bilan)">
                    </div>
                  </div>

                  <div class="alert alert-info py-2 px-3 small mb-0" style="font-size:0.8rem;">
                    💡 <b>Eslatma:</b> Faqat belgilangan guruhdagi o'quvchilar web portalda va botda testni ko'radi va topshira oladi.
                  </div>
                </div>
                <div class="modal-footer">
                  <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Ortga</button>
                  <button type="submit" class="btn btn-success fw-semibold">
                    {% if ex.is_active %}💾 Guruhlarni saqlash{% else %}▶ Testni yoqish{% endif %}
                  </button>
                </div>
              </form>
            </div>
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
function toggleAllGroups(allCb) {
  if (allCb.checked) {
    document.querySelectorAll('.group-check').forEach(cb => { cb.checked = false; });
  }
}
function onGroupChange() {
  const anyChecked = document.querySelectorAll('.group-check:checked').length > 0;
  if (anyChecked) {
    const allCb = document.getElementById('allGroupsCheck');
    if (allCb) allCb.checked = false;
  }
}
function toggleModalAllGroups(examId, allCb) {
  if (allCb.checked) {
    document.querySelectorAll('.modal-grp-' + examId).forEach(cb => { cb.checked = false; });
  }
}
function onModalGroupChange(examId) {
  const anyChecked = document.querySelectorAll('.modal-grp-' + examId + ':checked').length > 0;
  const allCb = document.getElementById('modalAll_' + examId);
  if (allCb && anyChecked) {
    allCb.checked = false;
  }
}
</script>
"""


@app.route("/admin/exams")
@admin_required
def exams_page():
    topics = db.list_topics_with_counts()
    grouped = {}
    for t in topics:
        grouped.setdefault(t["course_dir"], []).append(t)
    exams = db.list_exams()
    all_groups = db.get_all_student_groups()
    return render_page(
        EXAMS_HTML,
        active_tab="exams",
        grouped_topics=grouped,
        exams=exams,
        all_groups=all_groups,
    )


@app.route("/admin/exams/create", methods=["POST"])
@admin_required
def create_exam_route():
    try:
        topic_ids = [int(x) for x in request.form.getlist("topic_ids")]
        title = request.form.get("title", "")
        q_count = int(request.form.get("question_count", 15))
        pts = float(request.form.get("points_per_question", 5.0))
        max_att = int(request.form.get("max_attempts", 1))

        raw_groups = request.form.getlist("groups")
        custom_g = request.form.get("custom_groups", "").strip()
        final_groups = [g.strip() for g in raw_groups if g.strip()]
        if custom_g:
            for cg in custom_g.split(","):
                if cg.strip() and cg.strip() not in final_groups:
                    final_groups.append(cg.strip())

        exam = db.create_exam(
            title=title,
            topic_ids=topic_ids,
            question_count=q_count,
            points_per_question=pts,
            max_attempts=max_att,
            groups=final_groups,
        )
        flash(
            f"✅ '{exam['title']}' testi yaratildi ({len(topic_ids)} ta mavzu, {exam['question_count']} ta savol)!",
            "success",
        )
    except Exception as e:
        flash(f"❌ Test yaratishda xatolik: {e}", "danger")
    return redirect(url_for("exams_page"))


@app.route("/admin/exams/<int:exam_id>/toggle", methods=["POST"])
@admin_required
def toggle_exam_route(exam_id: int):
    action = request.form.get("action", "")
    if action == "stop":
        db.set_exam_active_status(exam_id, is_active=False)
        flash("⏸ Test to'xtatildi (yopildi).", "warning")
    elif action == "start":
        raw_groups = request.form.getlist("groups")
        custom_g = request.form.get("custom_groups", "").strip()
        final_groups = [g.strip() for g in raw_groups if g.strip()]
        if custom_g:
            for cg in custom_g.split(","):
                if cg.strip() and cg.strip() not in final_groups:
                    final_groups.append(cg.strip())

        db.set_exam_active_status(exam_id, is_active=True, groups=final_groups)
        groups_str = ", ".join(final_groups) if final_groups and "ALL" not in final_groups else "Barcha guruhlar"
        flash(f"✅ Test yoqildi! Guruhlar: {groups_str}", "success")
    else:
        # Xavfsiz fallback: agar action ko'rsatilmagan bo'lsa
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_active FROM exams WHERE id = %s;", (exam_id,))
                row = cur.fetchone()
                if row and row["is_active"]:
                    db.set_exam_active_status(exam_id, is_active=False)
                    flash("⏸ Test to'xtatildi (yopildi).", "warning")
                else:
                    db.set_exam_active_status(exam_id, is_active=True)
                    flash("✅ Test yoqildi! (Barcha guruhlar)", "success")

    return redirect(url_for("exams_page"))


@app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
@admin_required
def delete_exam_route(exam_id: int):
    db.delete_exam(exam_id)
    flash("🗑 Test o'chirildi.", "warning")
    return redirect(url_for("exams_page"))


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


@app.route("/admin/topics")
@admin_required
def topics_page():
    topics = db.list_topics_with_counts()
    return render_page(TOPICS_HTML, active_tab="topics", topics=topics)


@app.route("/admin/topics/add-question", methods=["POST"])
@admin_required
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


@app.route("/sync-html", methods=["POST"])
@admin_required
def sync_html_route():
    res = db.seed_topics_and_questions()
    flash(
        f"✅ Qo'llanma savollari yangilandi: {res['topics']} ta mavzu, {res['questions']} ta test savoli bazaga yuklandi!",
        "success",
    )
    return redirect(request.referrer or url_for("admin_dashboard"))


if __name__ == "__main__":
    db.seed_topics_and_questions()
    port = int(os.getenv("ADMIN_PORT", "5000"))
    print(f"🚀 web_fullstak Test Tizimi ishga tushdi: http://localhost:{port}")
    print(f"   - O'quvchilar web portali: http://localhost:{port}/student/login")
    print(f"   - O'qituvchi Admin Paneli: http://localhost:{port}/admin/login (Login: {ADMIN_USERNAME} / Parol: {ADMIN_PASSWORD})")
    app.run(host="0.0.0.0", port=port, debug=True)
