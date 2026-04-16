#!/bin/bash
# ============================================================
# ChessMaster UZ — Loyihani o'rnatish va ishga tushirish
# Python 3.11 kerak
# ============================================================

set -e

echo ""
echo "♛  ChessMaster UZ — O'rnatish boshlandi"
echo "============================================"

# 1. Virtual muhit
echo ""
echo "▶ 1. Virtual muhit yaratilmoqda..."
python3.11 -m venv venv
source venv/bin/activate
echo "   ✓ venv faollashtirildi"

# 2. Kutubxonalar
echo ""
echo "▶ 2. Kutubxonalar o'rnatilmoqda..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✓ Barcha kutubxonalar o'rnatildi"

# 3. Media papkasi
echo ""
echo "▶ 3. Papkalar yaratilmoqda..."
mkdir -p media/avatars
mkdir -p staticfiles
echo "   ✓ Papkalar tayyor"

# 4. Migrations
echo ""
echo "▶ 4. Ma'lumotlar bazasi yaratilmoqda..."
python manage.py makemigrations accounts chess chat
python manage.py migrate
echo "   ✓ Bazalar tayyor"

# 5. Static fayllar
echo ""
echo "▶ 5. Static fayllar yig'ilmoqda..."
python manage.py collectstatic --noinput -q
echo "   ✓ Static fayllar tayyor"

# 6. Superuser yaratish
echo ""
echo "▶ 6. Superuser yaratish"
echo "   (username, email, parol kiritasiz)"
python manage.py createsuperuser

echo ""
echo "============================================"
echo "✓  O'rnatish muvaffaqiyatli yakunlandi!"
echo ""
echo "▶ Serverni ishga tushirish:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo "▶ Manzillar:"
echo "   Platforma:  http://127.0.0.1:8000/"
echo "   Admin:      http://127.0.0.1:8000/admin-panel/"
echo "   Superuser:  http://127.0.0.1:8000/superuser/users/"
echo "   DJ Admin:   http://127.0.0.1:8000/django-admin/"
echo ""
echo "▶ Email sozlash: chessmaster/settings.py → EMAIL_HOST_USER"
echo "============================================"
