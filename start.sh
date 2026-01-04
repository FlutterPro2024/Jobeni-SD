#!/bin/bash

# 1. الانتقال لمجلد المشروع الرئيسي
cd /data/data/com.termux/files/home/jobeni-sD

# 2. التأكد من وجود مكتبة PostgreSQL داخل البيئة الافتراضية
echo "🔍 Checking dependencies..."
./venv/bin/pip install psycopg2-binary flask-migrate python-dotenv requests pdfplumber -q

# 3. تحديث قاعدة البيانات في Neon (Migration)
echo "🔄 Connecting to Neon PostgreSQL and updating schema..."
./venv/bin/python -m flask db upgrade

# 4. تشغيل السيرفر
echo "🚀 Jobeni SD is starting on http://0.0.0.0:5000"
./venv/bin/python run.py
