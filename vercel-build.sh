#!/bin/sh
set -eu

npm ci
npm run build

if [ "${VERCEL_ENV:-}" != "production" ]; then
  echo "VERCEL_ENV is '${VERCEL_ENV:-unset}', so migrations were not run."
  exit 0
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Production migration cannot run." >&2
  exit 1
fi

echo "Applying migrations to the production database."
if ! python manage.py migrate --noinput; then
  echo "Production migration failed. The build is stopping." >&2
  exit 1
fi

python manage.py ensure_demo_user
