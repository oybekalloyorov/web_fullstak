#!/usr/bin/env python3
"""
database.py — PostgreSQL ma'lumotlar bazasi bilan ishlash moduli va HTML qo'llanmalar parseri.

Jadvallar:
  1. topics          — web_fullstak qo'llanmasidagi barcha kurslar va mavzular (8-sinf, CS, Darslar)
  2. questions       — har bir mavzuga tegishli test savollari (4 variantli + izoh)
  3. students        — o'qituvchi admin paneldan kiritgan o'quvchilar (F.I.Sh, sinf, login, parol, telegram_id)
  4. exams           — o'qituvchi yaratgan testlar (nomi, nechta savol tushishi, har bir savol bali, urinishlar soni)
  5. exam_topics     — testga qaysi mavzular kiritilgani (Many-to-Many bog'lanish)
  6. exam_attempts   — o'quvchilarning ishlagan testlari va to'plagan ballari
  7. attempt_answers — o'quvchining testdagi har bir savolga bergan javobi
"""

import hashlib
import json
import os
import pathlib
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/web_fullstak_test",
)

BASE_DIR = pathlib.Path(__file__).resolve().parent
META_RE = re.compile(r"^\s*<!--(.*?)-->", re.S)


@contextmanager
def get_conn():
    """PostgreSQL bazasiga ulanish kontekst menejeri (RealDictCursor bilan)."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """Parolni SHA-256 orqali xeshlash."""
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


# =====================================================================
# 1. JADVALLARNI YARATISH (SXEMA)
# =====================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    course_dir VARCHAR(50) NOT NULL,
    course_name VARCHAR(150) NOT NULL,
    chapter VARCHAR(150) DEFAULT '',
    topic_number INT NOT NULL DEFAULT 1,
    slug VARCHAR(150) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option SMALLINT NOT NULL CHECK (correct_option BETWEEN 1 AND 4),
    explanation TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (topic_id, question_text)
);

CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    class_name VARCHAR(50) NOT NULL DEFAULT '8-sinf',
    login VARCHAR(80) UNIQUE NOT NULL,
    plain_password VARCHAR(100) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    telegram_id BIGINT UNIQUE NULL,
    telegram_username VARCHAR(100) DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exams (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    question_count INT NOT NULL CHECK (question_count > 0),
    points_per_question NUMERIC(6, 2) NOT NULL DEFAULT 5.00,
    max_attempts INT NOT NULL DEFAULT 1 CHECK (max_attempts > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_topics (
    exam_id INT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (exam_id, topic_id)
);

CREATE TABLE IF NOT EXISTS exam_groups (
    exam_id INT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    group_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (exam_id, group_name)
);
CREATE INDEX IF NOT EXISTS idx_exam_groups_name ON exam_groups(group_name);

CREATE TABLE IF NOT EXISTS exam_attempts (
    id SERIAL PRIMARY KEY,
    exam_id INT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    total_questions INT NOT NULL,
    correct_answers INT NOT NULL DEFAULT 0,
    score_points NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
    max_points NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
    percentage NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress', -- 'in_progress' | 'completed'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS attempt_answers (
    id SERIAL PRIMARY KEY,
    attempt_id INT NOT NULL REFERENCES exam_attempts(id) ON DELETE CASCADE,
    question_order INT NOT NULL,
    question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    selected_option SMALLINT NULL CHECK (selected_option IS NULL OR selected_option BETWEEN 1 AND 4),
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    answered_at TIMESTAMP NULL,
    UNIQUE (attempt_id, question_order)
);

CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic_id);
CREATE INDEX IF NOT EXISTS idx_students_login ON students(login);
CREATE INDEX IF NOT EXISTS idx_students_tg ON students(telegram_id);
CREATE INDEX IF NOT EXISTS idx_attempts_exam ON exam_attempts(exam_id);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON exam_attempts(student_id);
"""


def init_db() -> None:
    """Ma'lumotlar bazasi jadvallarini yaratish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


# =====================================================================
# 2. QO'LLANMALARDAN MAVZULAR VA SAVOLLARNI YUKLASH (SEEDER)
# =====================================================================

def _parse_html_meta(text: str) -> Dict[str, str]:
    m = META_RE.match(text)
    meta = {}
    if m:
        for part in m.group(1).split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta


def seed_topics_and_questions(
    repo_root: Optional[pathlib.Path] = None,
    seed_json_path: Optional[pathlib.Path] = None,
) -> Dict[str, int]:
    """
    1) Agar questions_seed.json mavjud bo'lsa, undagi 82 ta mavzu va 495 ta savolni yuklaydi.
    2) Agar web_fullstak repozitoriysining `src/` papkasi mavjud bo'lsa, HTML fayllardagi
       `<div class="quiz" data-answer="...">` savollarini ham bevosita o'qib bazaga qo'shadi.
    """
    init_db()
    if seed_json_path is None:
        seed_json_path = BASE_DIR / "questions_seed.json"
    if repo_root is None:
        repo_root = BASE_DIR

    topics_data: List[Dict[str, Any]] = []

    # 1. JSON fayldan o'qish
    if seed_json_path.exists():
        topics_data = json.loads(seed_json_path.read_text(encoding="utf-8"))

    # 2. Agar src/ papkasi mavjud bo'lsa, yangi yoki o'zgargan HTML savollarni ham o'qish
    src_dir = repo_root / "src"
    if src_dir.exists():
        by_slug = {t["slug"]: t for t in topics_data}
        courses = [
            ("8-sinf", "8-sinf: Web Full-stack kursi"),
            ("cs", "8-sinf: Computer Science Foundation"),
            ("darslar", "Full-stack qo'llanma"),
        ]
        for course_dir, course_name in courses:
            c_path = src_dir / course_dir
            if not c_path.exists():
                continue
            for idx, f in enumerate(sorted(c_path.glob("*.html")), 1):
                if f.name == "index.html":
                    continue
                raw = f.read_text(encoding="utf-8")
                meta = _parse_html_meta(raw)
                soup = BeautifulSoup(raw, "html.parser")
                slug = f"{course_dir}/{f.stem}"
                num_match = re.match(r"^(\d+)", f.stem)
                topic_num = int(num_match.group(1)) if num_match else idx

                html_questions = []
                for q in soup.select("div.quiz"):
                    ans = int(q.get("data-answer", "1"))
                    q_p = q.select_one("p.q")
                    q_text = q_p.get_text(" ", strip=True) if q_p else ""
                    opts = [li.get_text(" ", strip=True) for li in q.select("ol > li")]
                    exp_p = q.select_one("p.explain")
                    exp_text = exp_p.get_text(" ", strip=True) if exp_p else ""
                    if len(opts) == 4 and q_text:
                        html_questions.append({
                            "question": q_text,
                            "options": opts,
                            "correct": ans,
                            "explanation": exp_text,
                        })

                if slug in by_slug:
                    if html_questions:
                        by_slug[slug]["questions"] = html_questions
                else:
                    topics_data.append({
                        "course_dir": course_dir,
                        "course_name": course_name,
                        "chapter": meta.get("bob", meta.get("level", "")),
                        "topic_number": topic_num,
                        "slug": slug,
                        "title": meta.get("title", f.stem),
                        "questions": html_questions,
                    })

    inserted_topics = 0
    inserted_questions = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for t in topics_data:
                cur.execute(
                    """
                    INSERT INTO topics (course_dir, course_name, chapter, topic_number, slug, title)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        course_name = EXCLUDED.course_name,
                        chapter = EXCLUDED.chapter,
                        topic_number = EXCLUDED.topic_number,
                        title = EXCLUDED.title
                    RETURNING id;
                    """,
                    (
                        t["course_dir"],
                        t["course_name"],
                        t.get("chapter", ""),
                        t.get("topic_number", 1),
                        t["slug"],
                        t["title"],
                    ),
                )
                topic_id = cur.fetchone()["id"]
                inserted_topics += 1

                for q in t.get("questions", []):
                    opts = q["options"]
                    if len(opts) < 4:
                        continue
                    cur.execute(
                        """
                        INSERT INTO questions (
                            topic_id, question_text, option_a, option_b, option_c, option_d,
                            correct_option, explanation
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (topic_id, question_text) DO UPDATE SET
                            option_a = EXCLUDED.option_a,
                            option_b = EXCLUDED.option_b,
                            option_c = EXCLUDED.option_c,
                            option_d = EXCLUDED.option_d,
                            correct_option = EXCLUDED.correct_option,
                            explanation = EXCLUDED.explanation;
                        """,
                        (
                            topic_id,
                            q["question"],
                            opts[0],
                            opts[1],
                            opts[2],
                            opts[3],
                            int(q["correct"]),
                            q.get("explanation", ""),
                        ),
                    )
                    inserted_questions += 1

    return {"topics": inserted_topics, "questions": inserted_questions}


# =====================================================================
# 3. O'QUVCHILAR BILAN ISHLASH (LOGIN / PAROL BOSHQARUVI)
# =====================================================================

def create_student(full_name: str, class_name: str, login: str, password: str) -> Dict[str, Any]:
    """O'qituvchi admin paneldan yangi o'quvchi va uning login-parolini qo'shadi."""
    login_clean = login.strip().lower()
    pwd_clean = password.strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO students (full_name, class_name, login, plain_password, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    full_name.strip(),
                    class_name.strip(),
                    login_clean,
                    pwd_clean,
                    hash_password(pwd_clean),
                ),
            )
            return dict(cur.fetchone())


def update_student(
    student_id: int,
    full_name: str,
    class_name: str,
    login: str,
    password: str,
    is_active: bool = True,
) -> None:
    """O'quvchining F.I.Sh, sinfi yoki login-parolini yangilash."""
    login_clean = login.strip().lower()
    pwd_clean = password.strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE students
                SET full_name = %s,
                    class_name = %s,
                    login = %s,
                    plain_password = %s,
                    password_hash = %s,
                    is_active = %s
                WHERE id = %s;
                """,
                (
                    full_name.strip(),
                    class_name.strip(),
                    login_clean,
                    pwd_clean,
                    hash_password(pwd_clean),
                    is_active,
                    student_id,
                ),
            )


def unlink_student_telegram(student_id: int) -> None:
    """O'quvchining Telegram bog'lanishini uzish (boshqa akkauntdan kirishi uchun)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE students SET telegram_id = NULL, telegram_username = '' WHERE id = %s;",
                (student_id,),
            )


def delete_student(student_id: int) -> None:
    """O'quvchini o'chirish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s;", (student_id,))


def list_students(class_filter: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Admin panel uchun barcha o'quvchilar va ularning ishlagan testlari soni."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.*,
                       COUNT(a.id) FILTER (WHERE a.status = 'completed') AS completed_exams,
                       COALESCE(ROUND(AVG(a.percentage) FILTER (WHERE a.status = 'completed'), 1), 0) AS avg_percent
                FROM students s
                LEFT JOIN exam_attempts a ON a.student_id = s.id
                WHERE 1=1
            """
            params: List[Any] = []
            if class_filter:
                query += " AND s.class_name = %s"
                params.append(class_filter)
            if search:
                query += " AND (s.full_name ILIKE %s OR s.login ILIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            query += " GROUP BY s.id ORDER BY s.class_name, s.full_name;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def authenticate_student(
    login: str,
    password: str,
    telegram_id: int,
    telegram_username: str = "",
) -> Dict[str, Any]:
    """
    Telegram botda o'quvchi kiritgan login va parolni tekshiradi.
    Muvaffaqiyatli bo'lsa, telegram_id ni shu o'quvchiga bog'laydi.
    """
    login_clean = login.strip().lower()
    pwd_hash = hash_password(password)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM students WHERE login = %s AND password_hash = %s;",
                (login_clean, pwd_hash),
            )
            student = cur.fetchone()
            if not student:
                return {"ok": False, "error": "❌ Login yoki parol noto'g'ri! Qaytadan tekshirib kiriting."}
            if not student["is_active"]:
                return {"ok": False, "error": "⛔ Sizning akkauntingiz o'qituvchi tomonidan vaqtincha bloklangan."}
            if student["telegram_id"] and student["telegram_id"] != telegram_id:
                return {
                    "ok": False,
                    "error": "⚠️ Bu login-parol allaqachon boshqa Telegram akkauntga ulangan. O'qituvchiga murojaat qiling.",
                }

            # Shu telegram_id oldin boshqa profilga ulangan bo'lsa, uni bo'shatamiz
            cur.execute(
                "UPDATE students SET telegram_id = NULL, telegram_username = '' WHERE telegram_id = %s AND id != %s;",
                (telegram_id, student["id"]),
            )
            cur.execute(
                """
                UPDATE students
                SET telegram_id = %s, telegram_username = %s
                WHERE id = %s
                RETURNING *;
                """,
                (telegram_id, telegram_username or "", student["id"]),
            )
            updated = dict(cur.fetchone())
            return {"ok": True, "student": updated}


def get_student_by_telegram(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID bo'yicha tizimga kirgan o'quvchini topish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM students WHERE telegram_id = %s AND is_active = TRUE;",
                (telegram_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def logout_student_by_telegram(telegram_id: int) -> bool:
    """O'quvchi Telegram botdan /logout qilganda telegram_id bog'lanishini uzadi."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE students SET telegram_id = NULL, telegram_username = '' WHERE telegram_id = %s;",
                (telegram_id,),
            )
            return cur.rowcount > 0


# =====================================================================
# 4. MAVZULAR, SAVOLLAR VA O'QITUVCHI TESTLARI (EXAMS)
# =====================================================================

def list_topics_with_counts() -> List[Dict[str, Any]]:
    """Barcha mavzular va har bir mavzudagi savollar sonini qaytaradi."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.*, COUNT(q.id) AS question_count
                FROM topics t
                LEFT JOIN questions q ON q.topic_id = t.id
                GROUP BY t.id
                ORDER BY
                    CASE t.course_dir
                        WHEN '8-sinf' THEN 1
                        WHEN 'cs' THEN 2
                        WHEN 'darslar' THEN 3
                        ELSE 4
                    END,
                    t.topic_number, t.id;
                """
            )
            return [dict(r) for r in cur.fetchall()]


def add_custom_question(
    topic_id: int,
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: int,
    explanation: str = "",
) -> Dict[str, Any]:
    """O'qituvchi admin paneldan ixtiyoriy mavzuga yangi test savoli qo'shishi uchun."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO questions (
                    topic_id, question_text, option_a, option_b, option_c, option_d,
                    correct_option, explanation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (topic_id, question_text) DO UPDATE SET
                    option_a = EXCLUDED.option_a,
                    option_b = EXCLUDED.option_b,
                    option_c = EXCLUDED.option_c,
                    option_d = EXCLUDED.option_d,
                    correct_option = EXCLUDED.correct_option,
                    explanation = EXCLUDED.explanation
                RETURNING *;
                """,
                (
                    topic_id,
                    question_text.strip(),
                    option_a.strip(),
                    option_b.strip(),
                    option_c.strip(),
                    option_d.strip(),
                    int(correct_option),
                    explanation.strip(),
                ),
            )
            return dict(cur.fetchone())


def create_exam(
    title: str,
    topic_ids: List[int],
    question_count: int,
    points_per_question: float = 5.0,
    max_attempts: int = 1,
    description: str = "",
    groups: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    O'qituvchi qaysi va nechta mavzular bo'yicha test bo'lishini hamda
    testga nechta savol tushishini kiritib yangi test yaratadi.
    """
    if not topic_ids:
        raise ValueError("Kamida bitta mavzu tanlanishi shart!")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Tanlangan mavzularda yetarli savol borligini tekshiramiz
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM questions WHERE topic_id = ANY(%s);",
                (topic_ids,),
            )
            available = cur.fetchone()["cnt"]
            if available == 0:
                raise ValueError("Tanlangan mavzularda hozircha savollar yo'q!")
            actual_q_count = min(int(question_count), int(available))

            cur.execute(
                """
                INSERT INTO exams (title, description, question_count, points_per_question, max_attempts, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING *;
                """,
                (title.strip(), description.strip(), actual_q_count, points_per_question, max_attempts),
            )
            exam = dict(cur.fetchone())

            for tid in set(topic_ids):
                cur.execute(
                    "INSERT INTO exam_topics (exam_id, topic_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                    (exam["id"], int(tid)),
                )

            if groups:
                clean_groups = {g.strip() for g in groups if g.strip() and g.strip().upper() != "ALL"}
                for g in clean_groups:
                    cur.execute(
                        "INSERT INTO exam_groups (exam_id, group_name) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                        (exam["id"], g),
                    )

            return exam


def list_exams() -> List[Dict[str, Any]]:
    """Admin panel uchun barcha testlar, tanlangan mavzular ro'yxati va topshirganlar soni."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                       COUNT(DISTINCT et.topic_id) AS topic_count,
                       COALESCE(
                           STRING_AGG(DISTINCT (t.course_dir || '/' || LPAD(t.topic_number::text, 2, '0') || ': ' || t.title), ' • '),
                           ''
                       ) AS topics_summary,
                       COALESCE(
                           (SELECT STRING_AGG(eg.group_name, ', ' ORDER BY eg.group_name) FROM exam_groups eg WHERE eg.exam_id = e.id),
                           'Barcha guruhlar'
                       ) AS target_groups,
                       COALESCE(
                           (SELECT ARRAY_AGG(eg.group_name ORDER BY eg.group_name) FROM exam_groups eg WHERE eg.exam_id = e.id),
                           ARRAY[]::varchar[]
                       ) AS assigned_groups,
                       (
                           SELECT COUNT(*) FROM exam_attempts a
                           WHERE a.exam_id = e.id AND a.status = 'completed'
                       ) AS completed_count
                FROM exams e
                LEFT JOIN exam_topics et ON et.exam_id = e.id
                LEFT JOIN topics t ON t.id = et.topic_id
                GROUP BY e.id
                ORDER BY e.created_at DESC;
                """
            )
            return [dict(r) for r in cur.fetchall()]


def toggle_exam_status(exam_id: int) -> None:
    """Testni faollashtirish yoki to'xtatish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE exams SET is_active = NOT is_active WHERE id = %s;",
                (exam_id,),
            )


def set_exam_active_status(
    exam_id: int,
    is_active: bool,
    groups: Optional[List[str]] = None,
) -> None:
    """Testni yoqish yoki to'xtatish hamda tanlangan guruhlarni biriktirish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE exams SET is_active = %s WHERE id = %s;",
                (is_active, exam_id),
            )
            if is_active:
                cur.execute("DELETE FROM exam_groups WHERE exam_id = %s;", (exam_id,))
                if groups:
                    clean_groups = {g.strip() for g in groups if g.strip() and g.strip().upper() != "ALL"}
                    for g in clean_groups:
                        cur.execute(
                            "INSERT INTO exam_groups (exam_id, group_name) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                            (exam_id, g),
                        )


def delete_exam(exam_id: int) -> None:
    """Testni o'chirish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM exams WHERE id = %s;", (exam_id,))


def get_active_exams_for_student(student_id: int) -> List[Dict[str, Any]]:
    """O'quvchi uchun ochiq (faol) testlar va uning urinishlar holati."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                       COUNT(DISTINCT et.topic_id) AS topic_count,
                       STRING_AGG(DISTINCT t.title, ', ') AS topic_titles,
                       COALESCE(
                           (SELECT STRING_AGG(eg.group_name, ', ' ORDER BY eg.group_name) FROM exam_groups eg WHERE eg.exam_id = e.id),
                           'Barcha guruhlar'
                       ) AS target_groups,
                       COALESCE(
                           (SELECT ARRAY_AGG(eg.group_name ORDER BY eg.group_name) FROM exam_groups eg WHERE eg.exam_id = e.id),
                           ARRAY[]::varchar[]
                       ) AS assigned_groups,
                       (
                           SELECT COUNT(*) FROM exam_attempts a
                           WHERE a.exam_id = e.id AND a.student_id = %s AND a.status = 'completed'
                       ) AS used_attempts,
                       (
                           SELECT MAX(a.score_points) FROM exam_attempts a
                           WHERE a.exam_id = e.id AND a.student_id = %s AND a.status = 'completed'
                       ) AS best_score
                FROM exams e
                JOIN exam_topics et ON et.exam_id = e.id
                JOIN topics t ON t.id = et.topic_id
                JOIN students s ON s.id = %s
                WHERE e.is_active = TRUE
                  AND (
                      NOT EXISTS (SELECT 1 FROM exam_groups eg WHERE eg.exam_id = e.id)
                      OR EXISTS (SELECT 1 FROM exam_groups eg WHERE eg.exam_id = e.id AND eg.group_name = s.class_name)
                  )
                GROUP BY e.id
                ORDER BY e.created_at DESC;
                """,
                (student_id, student_id, student_id),
            )
            return [dict(r) for r in cur.fetchall()]


# =====================================================================
# 5. TEST TOPSHIRISH JARAYONI (TELEGRAM BOT UCHUN ENGINE)
# =====================================================================

def start_or_resume_attempt(student_id: int, exam_id: int) -> Dict[str, Any]:
    """
    O'quvchi testni boshlaganda:
    - Agar tugallanmagan (`in_progress`) urinishi bo'lsa, shuni davom ettiradi.
    - Aks holda urinishlar limitini tekshirib, o'qituvchi tanlagan mavzulardan
      tasodifiy `question_count` ta savol tanlab yangi urinish yaratadi.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM exams WHERE id = %s AND is_active = TRUE;", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                return {"ok": False, "error": "⚠️ Bu test hozirda faol emas yoki yopilgan."}

            # Guruh tekshiruvi:
            cur.execute("SELECT class_name FROM students WHERE id = %s;", (student_id,))
            st_info = cur.fetchone()
            if st_info:
                st_class = st_info["class_name"]
                cur.execute("SELECT 1 FROM exam_groups WHERE exam_id = %s;", (exam_id,))
                if cur.fetchone():
                    cur.execute(
                        "SELECT 1 FROM exam_groups WHERE exam_id = %s AND group_name = %s;",
                        (exam_id, st_class),
                    )
                    if not cur.fetchone():
                        return {
                            "ok": False,
                            "error": f"⛔ Ushbu test sizning guruhingiz ({st_class}) uchun mo'ljallanmagan.",
                        }

            # Tugallanmagan urinish bormi?
            cur.execute(
                """
                SELECT * FROM exam_attempts
                WHERE student_id = %s AND exam_id = %s AND status = 'in_progress'
                ORDER BY id DESC LIMIT 1;
                """,
                (student_id, exam_id),
            )
            in_prog = cur.fetchone()
            if in_prog:
                return {"ok": True, "attempt": dict(in_prog), "exam": dict(exam), "resumed": True}

            # Tugallangan urinishlar sonini tekshirish
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM exam_attempts
                WHERE student_id = %s AND exam_id = %s AND status = 'completed';
                """,
                (student_id, exam_id),
            )
            used = cur.fetchone()["cnt"]
            if used >= exam["max_attempts"]:
                return {
                    "ok": False,
                    "error": f"✅ Siz bu testni topshirib bo'lgansiz (ruxsat etilgan urinishlar soni: {exam['max_attempts']} ta).",
                }

            # O'qituvchi tanlagan mavzulardan tasodifiy savollar olish
            cur.execute(
                """
                SELECT q.id
                FROM questions q
                JOIN exam_topics et ON et.topic_id = q.topic_id
                WHERE et.exam_id = %s
                ORDER BY RANDOM()
                LIMIT %s;
                """,
                (exam_id, exam["question_count"]),
            )
            q_rows = cur.fetchall()
            if not q_rows:
                return {"ok": False, "error": "⚠️ Bu test mavzularida savollar topilmadi."}

            total_q = len(q_rows)
            max_pts = float(exam["points_per_question"]) * total_q

            cur.execute(
                """
                INSERT INTO exam_attempts (
                    exam_id, student_id, total_questions, max_points, status
                )
                VALUES (%s, %s, %s, %s, 'in_progress')
                RETURNING *;
                """,
                (exam_id, student_id, total_q, max_pts),
            )
            attempt = dict(cur.fetchone())

            for idx, qr in enumerate(q_rows, 1):
                cur.execute(
                    """
                    INSERT INTO attempt_answers (attempt_id, question_order, question_id)
                    VALUES (%s, %s, %s);
                    """,
                    (attempt["id"], idx, qr["id"]),
                )

            return {"ok": True, "attempt": attempt, "exam": dict(exam), "resumed": False}


def get_next_unanswered_question(attempt_id: int) -> Optional[Dict[str, Any]]:
    """Joriy urinishdagi navbatdagi javob berilmagan savolni qaytaradi."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT aa.id AS answer_row_id,
                       aa.question_order,
                       ea.total_questions,
                       q.id AS question_id,
                       q.question_text,
                       q.option_a,
                       q.option_b,
                       q.option_c,
                       q.option_d,
                       t.title AS topic_title,
                       t.course_name
                FROM attempt_answers aa
                JOIN exam_attempts ea ON ea.id = aa.attempt_id
                JOIN questions q ON q.id = aa.question_id
                JOIN topics t ON t.id = q.topic_id
                WHERE aa.attempt_id = %s AND aa.selected_option IS NULL
                ORDER BY aa.question_order ASC
                LIMIT 1;
                """,
                (attempt_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def submit_question_answer(
    attempt_id: int,
    question_order: int,
    selected_option: int,
) -> Dict[str, Any]:
    """
    O'quvchining javobini saqlaydi. Agar barcha savollarga javob berilgan bo'lsa,
    umumiy ball va foizni hisoblab urinishni 'completed' qiladi.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT aa.*, q.correct_option, q.explanation, q.question_text
                FROM attempt_answers aa
                JOIN questions q ON q.id = aa.question_id
                WHERE aa.attempt_id = %s AND aa.question_order = %s;
                """,
                (attempt_id, question_order),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "Savol topilmadi."}

            is_correct = int(selected_option) == int(row["correct_option"])
            cur.execute(
                """
                UPDATE attempt_answers
                SET selected_option = %s,
                    is_correct = %s,
                    answered_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (int(selected_option), is_correct, row["id"]),
            )

            # Javob berilmagan savol qoldimi?
            cur.execute(
                """
                SELECT COUNT(*) AS rem
                FROM attempt_answers
                WHERE attempt_id = %s AND selected_option IS NULL;
                """,
                (attempt_id,),
            )
            remaining = cur.fetchone()["rem"]

            if remaining == 0:
                # Test yakunlandi — ballarni hisoblaymiz
                cur.execute(
                    """
                    SELECT COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct_cnt,
                           COUNT(*) AS total_cnt
                    FROM attempt_answers
                    WHERE attempt_id = %s;
                    """,
                    (attempt_id,),
                )
                counts = cur.fetchone()
                correct_cnt = int(counts["correct_cnt"])
                total_cnt = int(counts["total_cnt"])

                cur.execute(
                    """
                    SELECT e.points_per_question, e.title AS exam_title
                    FROM exam_attempts ea
                    JOIN exams e ON e.id = ea.exam_id
                    WHERE ea.id = %s;
                    """,
                    (attempt_id,),
                )
                exam_info = cur.fetchone()
                pts_per_q = float(exam_info["points_per_question"])
                score_pts = round(correct_cnt * pts_per_q, 2)
                max_pts = round(total_cnt * pts_per_q, 2)
                pct = round((correct_cnt / total_cnt) * 100, 2) if total_cnt > 0 else 0.0

                cur.execute(
                    """
                    UPDATE exam_attempts
                    SET correct_answers = %s,
                        score_points = %s,
                        max_points = %s,
                        percentage = %s,
                        status = 'completed',
                        finished_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *;
                    """,
                    (correct_cnt, score_pts, max_pts, pct, attempt_id),
                )
                finished_attempt = dict(cur.fetchone())
                finished_attempt["exam_title"] = exam_info["exam_title"]
                return {
                    "ok": True,
                    "is_correct": is_correct,
                    "correct_option": row["correct_option"],
                    "explanation": row["explanation"],
                    "completed": True,
                    "result": finished_attempt,
                }

            return {
                "ok": True,
                "is_correct": is_correct,
                "correct_option": row["correct_option"],
                "explanation": row["explanation"],
                "completed": False,
            }


# =====================================================================
# 6. NATIJALAR VA ADMIN PANEL STATISTIKASI
# =====================================================================

def list_student_attempts(student_id: int) -> List[Dict[str, Any]]:
    """O'quvchining o'zi ishlagan barcha test natijalari."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ea.*, e.title AS exam_title
                FROM exam_attempts ea
                JOIN exams e ON e.id = ea.exam_id
                WHERE ea.student_id = %s AND ea.status = 'completed'
                ORDER BY ea.finished_at DESC;
                """,
                (student_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def list_all_results(
    exam_id: Optional[int] = None,
    class_name: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Admin panelda kim qancha ball olganini ko'rsatuvchi natijalar jadvali."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT ea.id AS attempt_id,
                       ea.total_questions,
                       ea.correct_answers,
                       ea.score_points,
                       ea.max_points,
                       ea.percentage,
                       ea.status,
                       ea.started_at,
                       ea.finished_at,
                       s.id AS student_id,
                       s.full_name,
                       s.class_name,
                       s.login,
                       e.id AS exam_id,
                       e.title AS exam_title,
                       (
                           SELECT COUNT(*) FROM exam_topics et WHERE et.exam_id = e.id
                       ) AS topic_count
                FROM exam_attempts ea
                JOIN students s ON s.id = ea.student_id
                JOIN exams e ON e.id = ea.exam_id
                WHERE 1=1
            """
            params: List[Any] = []
            if exam_id:
                query += " AND ea.exam_id = %s"
                params.append(int(exam_id))
            if class_name:
                query += " AND s.class_name = %s"
                params.append(class_name)
            if search:
                query += " AND (s.full_name ILIKE %s OR s.login ILIKE %s OR e.title ILIKE %s)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            query += " ORDER BY ea.score_points DESC, ea.finished_at DESC NULLS LAST;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def get_attempt_detail(attempt_id: int) -> Dict[str, Any]:
    """Admin panelda o'quvchining har bir savolga bergan javobini batafsil ko'rish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ea.*, s.full_name, s.class_name, s.login, e.title AS exam_title
                FROM exam_attempts ea
                JOIN students s ON s.id = ea.student_id
                JOIN exams e ON e.id = ea.exam_id
                WHERE ea.id = %s;
                """,
                (attempt_id,),
            )
            info = cur.fetchone()
            if not info:
                return {}

            cur.execute(
                """
                SELECT aa.question_order,
                       aa.selected_option,
                       aa.is_correct,
                       q.question_text,
                       q.option_a,
                       q.option_b,
                       q.option_c,
                       q.option_d,
                       q.correct_option,
                       q.explanation,
                       t.title AS topic_title
                FROM attempt_answers aa
                JOIN questions q ON q.id = aa.question_id
                JOIN topics t ON t.id = q.topic_id
                WHERE aa.attempt_id = %s
                ORDER BY aa.question_order ASC;
                """,
                (attempt_id,),
            )
            answers = [dict(r) for r in cur.fetchall()]
            result = dict(info)
            result["answers"] = answers
            return result


def get_dashboard_stats() -> Dict[str, Any]:
    """Admin panel bosh sahifasi uchun tezkor ko'rsatkichlar."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM topics;")
            topics_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM questions;")
            questions_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM students;")
            students_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM exams WHERE is_active = TRUE;")
            active_exams_cnt = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM exam_attempts WHERE status = 'completed';")
            completed_attempts_cnt = cur.fetchone()["c"]
            cur.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name;")
            classes = [r["class_name"] for r in cur.fetchall()]
            return {
                "topics_count": topics_cnt,
                "questions_count": questions_cnt,
                "students_count": students_cnt,
                "active_exams_count": active_exams_cnt,
                "completed_attempts_count": completed_attempts_cnt,
                "classes": classes,
            }




def authenticate_student_web(login: str, password: str) -> Dict[str, Any]:
    """
    O'quvchi web sahifadan login va parol bilan kirganda tekshirish.
    """
    login_clean = login.strip().lower()
    pwd_hash = hash_password(password)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM students WHERE login = %s AND password_hash = %s;",
                (login_clean, pwd_hash),
            )
            student = cur.fetchone()
            if not student:
                return {"ok": False, "error": "Login yoki parol noto'g'ri! Qaytadan tekshirib kiriting."}
            if not student["is_active"]:
                return {"ok": False, "error": "Sizning akkauntingiz o'qituvchi tomonidan vaqtincha bloklangan."}
            return {"ok": True, "student": dict(student)}


def get_student_by_id(student_id: int) -> Optional[Dict[str, Any]]:
    """ID bo'yicha o'quvchi ma'lumotlarini olish."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id = %s;", (student_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def change_student_password(student_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
    """
    O'quvchi o'z profilida faqat parolini o'zgartira oladi.
    Eski parol to'g'riligi tekshiriladi, yangi parol kamida 4 belgidan iborat bo'lishi kerak.
    """
    new_pwd = new_password.strip()
    if len(new_pwd) < 4:
        return {"ok": False, "error": "Yangi parol kamida 4 ta belgidan iborat bo'lishi kerak!"}

    old_hash = hash_password(old_password)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM students WHERE id = %s AND password_hash = %s;",
                (student_id, old_hash),
            )
            if not cur.fetchone():
                return {"ok": False, "error": "Joriy (eski) parol noto'g'ri kiritildi!"}

            new_hash = hash_password(new_pwd)
            cur.execute(
                """
                UPDATE students
                SET plain_password = %s,
                    password_hash = %s
                WHERE id = %s;
                """,
                (new_pwd, new_hash, student_id),
            )
            return {"ok": True}


def get_attempt_for_web(attempt_id: int) -> Optional[Dict[str, Any]]:
    """
    Web interfeys orqali test ishlash uchun urinish ma'lumotlari,
    barcha savollar, o'quvchi javoblari va joriy statistika.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ea.*, e.title AS exam_title, e.points_per_question, e.description AS exam_desc,
                       s.full_name, s.class_name, s.login
                FROM exam_attempts ea
                JOIN exams e ON e.id = ea.exam_id
                JOIN students s ON s.id = ea.student_id
                WHERE ea.id = %s;
                """,
                (attempt_id,),
            )
            attempt = cur.fetchone()
            if not attempt:
                return None

            cur.execute(
                """
                SELECT aa.id AS answer_row_id,
                       aa.question_order,
                       aa.selected_option,
                       aa.is_correct,
                       aa.answered_at,
                       q.id AS question_id,
                       q.question_text,
                       q.option_a,
                       q.option_b,
                       q.option_c,
                       q.option_d,
                       q.correct_option,
                       q.explanation,
                       t.title AS topic_title,
                       t.course_name
                FROM attempt_answers aa
                JOIN questions q ON q.id = aa.question_id
                JOIN topics t ON t.id = q.topic_id
                WHERE aa.attempt_id = %s
                ORDER BY aa.question_order ASC;
                """,
                (attempt_id,),
            )
            questions = [dict(r) for r in cur.fetchall()]
            res = dict(attempt)
            res["questions"] = questions
            res["answered_count"] = sum(1 for q in questions if q["selected_option"] is not None)
            return res


def finish_attempt_force(attempt_id: int) -> Dict[str, Any]:
    """
    O'quvchi 'Testni yakunlash' tugmasini bosganda testni darhol baholash va yakunlash.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct_cnt,
                       COUNT(*) AS total_cnt
                FROM attempt_answers
                WHERE attempt_id = %s;
                """,
                (attempt_id,),
            )
            counts = cur.fetchone()
            correct_cnt = int(counts["correct_cnt"])
            total_cnt = int(counts["total_cnt"])

            cur.execute(
                """
                SELECT e.points_per_question, e.title AS exam_title
                FROM exam_attempts ea
                JOIN exams e ON e.id = ea.exam_id
                WHERE ea.id = %s;
                """,
                (attempt_id,),
            )
            exam_info = cur.fetchone()
            pts_per_q = float(exam_info["points_per_question"])
            score_pts = round(correct_cnt * pts_per_q, 2)
            max_pts = round(total_cnt * pts_per_q, 2)
            pct = round((correct_cnt / total_cnt) * 100, 2) if total_cnt > 0 else 0.0

            cur.execute(
                """
                UPDATE exam_attempts
                SET correct_answers = %s,
                    score_points = %s,
                    max_points = %s,
                    percentage = %s,
                    status = 'completed',
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *;
                """,
                (correct_cnt, score_pts, max_pts, pct, attempt_id),
            )
            finished = dict(cur.fetchone())
            finished["exam_title"] = exam_info["exam_title"]
            return {"ok": True, "result": finished}




def get_all_student_groups() -> List[str]:
    """Tizimda mavjud barcha guruhlar (sinflar) ro'yxati."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT class_name FROM students WHERE class_name <> '' ORDER BY class_name;")
            return [r["class_name"] for r in cur.fetchall()]


def bulk_import_students(raw_text: str) -> Dict[str, Any]:
    """
    O'qituvchi tomonidan vergul, nuqta-vergul yoki tab bilan ajratilgan
    o'quvchilar ro'yxatini avtomatik bazaga qo'shish.
    Format: Guruh, F.I.Sh, [Login], [Parol]

    DIQQAT: Tizimdagi mavjud o'quvchilar hech qachon yangilanmaydi yoki o'chirilmaydi!
    Agar kiritilgan login oldinroq boshqa o'quvchi tomonidan band qilingan bo'lsa,
    yangi o'quvchining loginiga avtomatik tarzda uning familiyasi yoki guruhi qo'shilib,
    u yangi alohida o'quvchi sifatida bazaga qo'shiladi.
    """
    import random

    lines = raw_text.strip().splitlines()
    added = 0
    errors = []
    processed = []
    adjusted = []

    def make_login(name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_") or "oquvchi"
        return f"{base}_{random.randint(100, 999)}"

    def make_password() -> str:
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
        return "".join(random.choice(chars) for _ in range(6))

    with get_conn() as conn:
        with conn.cursor() as cur:
            for line_no, raw_line in enumerate(lines, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                if "\t" in line:
                    parts = [p.strip() for p in line.split("\t")]
                elif ";" in line:
                    parts = [p.strip() for p in line.split(";")]
                else:
                    parts = [p.strip() for p in line.split(",")]

                if len(parts) < 2:
                    errors.append(f"{line_no}-qator: Kamida Guruh va F.I.Sh kiritilishi kerak ('{line}')")
                    continue

                # Sarlavha qatori (header) bo'lsa o'tkazib yuboramiz
                if parts[0].lower() in ["guruh", "sinf", "class", "group"] and parts[1].lower() in ["fish", "f.i.sh", "ism", "name"]:
                    continue

                class_name = parts[0]
                full_name = parts[1]
                desired_login = parts[2].lower() if len(parts) >= 3 and parts[2] else make_login(full_name)
                password = parts[3] if len(parts) >= 4 and parts[3] else make_password()

                # Unikal login tanlash (mavjud o'quvchini aslo yangilamaymiz!)
                candidate_login = desired_login
                counter = 1
                words = [re.sub(r"[^a-z0-9]+", "", w.lower().strip()) for w in full_name.split() if w.strip()]
                surname = words[0] if words else ""
                grp_slug = re.sub(r"[^a-z0-9]+", "_", class_name.lower().strip()).strip("_")

                while True:
                    cur.execute("SELECT id FROM students WHERE login = %s;", (candidate_login,))
                    if not cur.fetchone():
                        break
                    # Login band bo'lsa, ketma-ketlik bo'yicha unikal nom beramiz:
                    if counter == 1 and surname and surname != desired_login:
                        candidate_login = f"{desired_login}_{surname}"
                    elif counter == 2 and grp_slug:
                        candidate_login = f"{desired_login}_{grp_slug}"
                    elif counter == 3 and surname:
                        candidate_login = f"{surname}_{desired_login}"
                    else:
                        candidate_login = f"{desired_login}_{counter}"
                    counter += 1

                if candidate_login != desired_login:
                    adjusted.append({
                        "full_name": full_name,
                        "class_name": class_name,
                        "original_login": desired_login,
                        "login": candidate_login,
                    })

                login = candidate_login
                pwd_hash = hash_password(password)

                # Har doim YANGI o'quvchi sifatida qo'shamiz
                cur.execute(
                    """
                    INSERT INTO students (full_name, class_name, login, plain_password, password_hash)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (full_name, class_name, login, password, pwd_hash),
                )
                added += 1

                processed.append({
                    "class_name": class_name,
                    "full_name": full_name,
                    "login": login,
                    "password": password,
                    "adjusted": (candidate_login != desired_login),
                })

    return {
        "total": len(processed),
        "added": added,
        "adjusted": adjusted,
        "errors": errors,
        "students": processed,
    }


if __name__ == "__main__":
    print("PostgreSQL jadvallari yaratilmoqda va qo'llanma savollari yuklanmoqda...")
    stats = seed_topics_and_questions()
    print(f"Tayyor! Yuklangan mavzular: {stats['topics']} ta, savollar: {stats['questions']} ta.")
