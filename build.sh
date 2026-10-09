#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
npm ci --include=dev
npm run build
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py ensure_demo_user
