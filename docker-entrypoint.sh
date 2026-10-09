#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py ensure_demo_user
exec gunicorn rabbit_herd.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
