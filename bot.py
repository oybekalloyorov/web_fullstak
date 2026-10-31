#!/usr/bin/env python3
"""
bot.py — O'quvchilar uchun Telegram Test Bot (aiogram 3.x + PostgreSQL).

Ishlash tartibi:
  1. O'quvchi /start bosadi va o'qituvchi admin panelda bergan shaxsiy Login hamda Parolini kiritadi.
  2. Tizimga kirgach, o'qituvchi faollashtirgan testlar ro'yxatini (qaysi mavzular va nechta savol borligini) ko'radi.
  3. Testni boshlab, savollarga inline tugmalar (1, 2, 3, 4) orqali javob beradi.
  4. Test yakunida o'quvchining to'g'ri javoblari soni, to'plagan bali va bahosi hisoblanib PostgreSQL bazasiga
     yoziladi hamda o'qituvchining Admin Panelida darhol ko'rinadi.

Ishga tushirish:
  python3 bot.py
"""

import asyncio
import html
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv

import database as db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
router = Router()


class AuthStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Mavjud testlarni ishlash")],
            [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="👤 Profilim")],
            [KeyboardButton(text="🚪 Tizimdan chiqish")],
        ],
        resize_keyboard=True,
    )


def format_question_message(q_data: dict) -> str:
    """Savol va 4 ta variantni chiroyli HTML ko'rinishida tayyorlash."""
    order = q_data["question_order"]
    total = q_data["total_questions"]
    topic = html.escape(q_data["topic_title"])
    q_text = html.escape(q_data["question_text"])
    opt_a = html.escape(q_data["option_a"])
    opt_b = html.escape(q_data["option_b"])
    opt_c = html.escape(q_data["option_c"])
    opt_d = html.escape(q_data["option_d"])

    return (
        f"❓ <b>Savol: {order} / {total}</b>\n"
        f"📘 <i>Mavzu: {topic}</i>\n\n"
        f"<b>{q_text}</b>\n\n"
        f"<b>1)</b> {opt_a}\n"
        f"<b>2)</b> {opt_b}\n"
        f"<b>3)</b> {opt_c}\n"
        f"<b>4)</b> {opt_d}\n\n"
        f"👇 Quyidagi tugmalardan to'g'ri javob raqamini tanlang:"
    )


def question_inline_kb(attempt_id: int, question_order: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1️⃣ - variant",
                    callback_data=f"ans:{attempt_id}:{question_order}:1",
                ),
                InlineKeyboardButton(
                    text="2️⃣ - variant",
                    callback_data=f"ans:{attempt_id}:{question_order}:2",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="3️⃣ - variant",
                    callback_data=f"ans:{attempt_id}:{question_order}:3",
                ),
                InlineKeyboardButton(
                    text="4️⃣ - variant",
                    callback_data=f"ans:{attempt_id}:{question_order}:4",
                ),
            ],
        ]
    )


def grade_label(percentage: float) -> str:
    if percentage >= 86:
        return "🏆 5 baho (A'lo)"
    if percentage >= 71:
        return "👍 4 baho (Yaxshi)"
    if percentage >= 55:
        return "🙂 3 baho (Qoniqarli)"
    return "📖 2 baho (Mavzularni takrorlang)"


# =====================================================================
# 1. /START VA LOGIN-PAROL ORQALI TIZIMGA KIRISH
# =====================================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    student = db.get_student_by_telegram(message.from_user.id)
    if student:
        await message.answer(
            f"👋 Salom, <b>{html.escape(student['full_name'])}</b> ({html.escape(student['class_name'])})!\n\n"
            f"O'qituvchi belgilagan mavzular bo'yicha test ishlash uchun quyidagi menyudan foydalaning:",
            reply_markup=main_menu_kb(),
        )
        return

    await state.set_state(AuthStates.waiting_for_login)
    await message.answer(
        "🎓 <b>web_fullstak — O'quvchilar test tizimiga xush kelibsiz!</b>\n\n"
        "Test ishlash uchun o'qituvchi sizga bergan shaxsiy <b>Login</b>ni kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AuthStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    login_val = (message.text or "").strip()
    if not login_val or login_val.startswith("/"):
        await message.answer("Iltimos, loginni oddiy matn ko'rinishida yuboring:")
        return

    await state.update_data(login=login_val)
    await state.set_state(AuthStates.waiting_for_password)
    await message.answer(
        f"👤 Login: <code>{html.escape(login_val)}</code>\n"
        f"🔑 Endi shaxsiy <b>Parol</b>ingizni kiriting:"
    )


@router.message(AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    password_val = (message.text or "").strip()
    data = await state.get_data()
    login_val = data.get("login", "")

    # Xavfsizlik uchun o'quvchi yozgan parol xabarini o'chirishga harakat qilamiz
    try:
        await message.delete()
    except Exception:
        pass

    auth = db.authenticate_student(
        login=login_val,
        password=password_val,
        telegram_id=message.from_user.id,
        telegram_username=message.from_user.username or "",
    )

    if not auth["ok"]:
        await state.set_state(AuthStates.waiting_for_login)
        await message.answer(
            f"{auth['error']}\n\n🔄 Iltimos, <b>Login</b>ingizni qaytadan kiriting:"
        )
        return

    await state.clear()
    student = auth["student"]
    await message.answer(
        f"✅ <b>Tizimga muvaffaqiyatli kirdingiz!</b>\n\n"
        f"👨‍🎓 O'quvchi: <b>{html.escape(student['full_name'])}</b>\n"
        f"🏫 Sinf: <b>{html.escape(student['class_name'])}</b>\n\n"
        f"Endi <b>«📝 Mavjud testlarni ishlash»</b> tugmasini bosib testni boshlashingiz mumkin:",
        reply_markup=main_menu_kb(),
    )


# =====================================================================
# 2. MAVJUD TESTLAR RO'YXATI VA TESTNI BOSHLASH
# =====================================================================

@router.message(F.text == "📝 Mavjud testlarni ishlash")
@router.message(Command("testlar"))
async def show_active_exams(message: Message):
    student = db.get_student_by_telegram(message.from_user.id)
    if not student:
        await message.answer("Avval /start buyrug'i orqali login va parolingiz bilan kiring.")
        return

    exams = db.get_active_exams_for_student(student["id"])
    if not exams:
        await message.answer("📭 Hozirda o'qituvchi tomonidan faollashtirilgan testlar yo'q.")
        return

    for ex in exams:
        max_pts = round(float(ex["question_count"]) * float(ex["points_per_question"]), 1)
        used = ex["used_attempts"]
        max_att = ex["max_attempts"]
        topics_str = html.escape(ex["topic_titles"] or "")
        if len(topics_str) > 320:
            topics_str = topics_str[:320] + "..."

        text = (
            f"📋 <b>{html.escape(ex['title'])}</b>\n\n"
            f"📚 <b>Kiritilgan mavzular ({ex['topic_count']} ta):</b>\n<i>{topics_str}</i>\n\n"
            f"❓ Savollar soni: <b>{ex['question_count']} ta</b>\n"
            f"🏆 Maksimal ball: <b>{max_pts} ball</b> (har bir savol {ex['points_per_question']} ball)\n"
            f"🔄 Urinishlar: <b>{used} / {max_att}</b>\n"
            f"👥 Guruh: <b>{html.escape(ex.get('target_groups', 'Barcha guruhlar'))}</b>"
        )
        if ex["best_score"] is not None:
            text += f"\n⭐️ Sizning natijangiz: <b>{ex['best_score']} ball</b>"

        if used < max_att:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="▶️ Testni boshlash",
                            callback_data=f"start_exam:{ex['id']}",
                        )
                    ]
                ]
            )
        else:
            kb = None

        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("start_exam:"))
async def cb_start_exam(callback: CallbackQuery):
    student = db.get_student_by_telegram(callback.from_user.id)
    if not student:
        await callback.answer("Avval /start orqali tizimga kiring!", show_alert=True)
        return

    exam_id = int(callback.data.split(":")[1])
    res = db.start_or_resume_attempt(student["id"], exam_id)
    if not res["ok"]:
        await callback.answer(res["error"], show_alert=True)
        return

    attempt = res["attempt"]
    next_q = db.get_next_unanswered_question(attempt["id"])
    if not next_q:
        await callback.answer("Ushbu urinishdagi barcha savollarga javob berilgan.", show_alert=True)
        return

    await callback.answer("Omad! Test boshlandi 🚀")
    await callback.message.edit_text(
        format_question_message(next_q),
        reply_markup=question_inline_kb(attempt["id"], next_q["question_order"]),
    )


# =====================================================================
# 3. SAVOLLARGA JAVOB BERISH VA BALLNI HISOBLASH
# =====================================================================

@router.callback_query(F.data.startswith("ans:"))
async def cb_answer_question(callback: CallbackQuery):
    student = db.get_student_by_telegram(callback.from_user.id)
    if not student:
        await callback.answer("Avval tizimga kiring!", show_alert=True)
        return

    _, attempt_id_str, q_order_str, opt_str = callback.data.split(":")
    attempt_id = int(attempt_id_str)
    q_order = int(q_order_str)
    selected_opt = int(opt_str)

    submit_res = db.submit_question_answer(attempt_id, q_order, selected_opt)
    if not submit_res["ok"]:
        await callback.answer(submit_res.get("error", "Xatolik"), show_alert=True)
        return

    # Agar barcha savollar yakunlangan bo'lsa
    if submit_res["completed"]:
        result = submit_res["result"]
        grade = grade_label(float(result["percentage"]))
        summary_text = (
            f"🎉 <b>Test yakunlandi!</b>\n\n"
            f"📋 Test: <b>{html.escape(result['exam_title'])}</b>\n"
            f"👨‍🎓 O'quvchi: <b>{html.escape(student['full_name'])}</b> ({html.escape(student['class_name'])})\n\n"
            f"✅ To'g'ri javoblar: <b>{result['correct_answers']} / {result['total_questions']} ta</b>\n"
            f"🏆 To'plagan balingiz: <b>{result['score_points']} / {result['max_points']} ball</b>\n"
            f"📊 Ko'rsatkich: <b>{result['percentage']}%</b> — {grade}\n\n"
            f"<i>Natijangiz o'qituvchi Admin Paneliga avtomatik yuborildi!</i>"
        )
        review_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔍 Xatolar va izohlarni ko'rish",
                        callback_data=f"review:{attempt_id}",
                    )
                ]
            ]
        )
        await callback.answer("Test yakunlandi! 🏁")
        await callback.message.edit_text(summary_text, reply_markup=review_kb)
        return

    # Navbatdagi savolga o'tish
    next_q = db.get_next_unanswered_question(attempt_id)
    if next_q:
        await callback.answer("Javob qabul qilindi ✓")
        await callback.message.edit_text(
            format_question_message(next_q),
            reply_markup=question_inline_kb(attempt_id, next_q["question_order"]),
        )


@router.callback_query(F.data.startswith("review:"))
async def cb_review_attempt(callback: CallbackQuery):
    attempt_id = int(callback.data.split(":")[1])
    detail = db.get_attempt_detail(attempt_id)
    if not detail:
        await callback.answer("Ma'lumot topilmadi.", show_alert=True)
        return

    lines = [f"🔍 <b>«{html.escape(detail['exam_title'])}» testi tahlili:</b>\n"]
    for a in detail["answers"]:
        opts = [a["option_a"], a["option_b"], a["option_c"], a["option_d"]]
        corr_idx = int(a["correct_option"]) - 1
        sel_idx = (int(a["selected_option"]) - 1) if a["selected_option"] else -1
        icon = "✅" if a["is_correct"] else "❌"
        block = f"{icon} <b>{a['question_order']}. {html.escape(a['question_text'])}</b>\n"
        if not a["is_correct"] and 0 <= sel_idx < 4:
            block += f"   Sizning javobingiz: <s>{html.escape(opts[sel_idx])}</s>\n"
        if 0 <= corr_idx < 4:
            block += f"   To'g'ri javob: <b>{html.escape(opts[corr_idx])}</b>\n"
        if a.get("explanation"):
            block += f"   💡 <i>{html.escape(a['explanation'])}</i>\n"
        lines.append(block)

    full_text = "\n".join(lines)
    # Telegram xabar uzunligi 4096 belgidan oshmasligi uchun bo'laklab yuboramiz
    await callback.answer()
    for i in range(0, len(full_text), 3800):
        await callback.message.answer(full_text[i : i + 3800])


# =====================================================================
# 4. O'QUVCHINING SHAXSIY NATIJALARI, PROFILI VA CHIQISH
# =====================================================================

@router.message(F.text == "📊 Mening natijalarim")
@router.message(Command("natijalarim"))
async def show_my_results(message: Message):
    student = db.get_student_by_telegram(message.from_user.id)
    if not student:
        await message.answer("Avval /start orqali login va parolingiz bilan kiring.")
        return

    attempts = db.list_student_attempts(student["id"])
    if not attempts:
        await message.answer("📭 Siz hali birorta ham test yakunlamagansiz.")
        return

    lines = [f"📊 <b>{html.escape(student['full_name'])} — ishlagan testlaringiz:</b>\n"]
    for idx, a in enumerate(attempts, 1):
        dt = a["finished_at"].strftime("%d.%m.%Y %H:%M") if a["finished_at"] else ""
        lines.append(
            f"<b>{idx}. {html.escape(a['exam_title'])}</b>\n"
            f"   ✅ To'g'ri: {a['correct_answers']}/{a['total_questions']} ta | "
            f"🏆 Ball: <b>{a['score_points']} / {a['max_points']}</b> ({a['percentage']}%)\n"
            f"   🕒 Vaqt: {dt}\n"
        )
    await message.answer("\n".join(lines))


@router.message(F.text == "👤 Profilim")
async def show_profile(message: Message):
    student = db.get_student_by_telegram(message.from_user.id)
    if not student:
        await message.answer("Avval /start orqali tizimga kiring.")
        return

    await message.answer(
        f"👤 <b>Sizning profilingiz:</b>\n\n"
        f"👨‍🎓 F.I.Sh: <b>{html.escape(student['full_name'])}</b>\n"
        f"🏫 Sinf: <b>{html.escape(student['class_name'])}</b>\n"
        f"🔑 Login: <code>{html.escape(student['login'])}</code>\n\n"
        f"Boshqa akkauntga o'tish uchun «🚪 Tizimdan chiqish» tugmasini bosing."
    )


@router.message(F.text == "🚪 Tizimdan chiqish")
@router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext):
    await state.clear()
    db.logout_student_by_telegram(message.from_user.id)
    await message.answer(
        "🚪 Tizimdan chiqdingiz. Qayta kirish uchun /start buyrug'ini bosing.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi! .env fayliga BOT_TOKEN=123456:ABC... qiymatini yozing."
        )
    # Ishga tushishdan oldin PostgreSQL jadvallari va qo'llanma savollarini tekshiramiz
    db.seed_topics_and_questions()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("🤖 Telegram Test Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())