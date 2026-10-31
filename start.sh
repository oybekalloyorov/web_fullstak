#!/usr/bin/env bash
set -e

echo "=== 1. PostgreSQL bazani tekshirish va savollarni yuklash ==="
python3 -c "import database; database.seed_topics_and_questions()"

echo "=== 2. Telegram botni ishga tushirish ==="
if [ -n "$BOT_TOKEN" ]; then
    python3 bot.py &
    echo "Telegram bot orqa fonda yoqildi!"
else
    echo "BOT_TOKEN topilmadi, bot yoqilmadi."
fi

echo "=== 3. Web serverni ishga tushirish ==="
exec gunicorn admin_panel:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120
