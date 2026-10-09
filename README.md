# Rabbit Herd

Rabbit Herd is a private record keeper for a small rabbitry.

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Leave `DATABASE_URL` unset in `.env` to use a local SQLite file. Set it to a Postgres URL when you have a database. `npm run watch` rebuilds the stylesheet and script while you work. Open http://localhost:8000.

## Environment variables

| Variable | Purpose |
|---|---|
| `DEBUG` | `true` for local development. Leave unset, or set `false`, on the host. |
| `SECRET_KEY` | Long random string. Required when `DEBUG` is off. |
| `DATABASE_URL` | Postgres connection string. SQLite is used only when this is unset. |
| `ALLOWED_HOSTS` | Comma-separated host names. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, including the scheme. |

On Render, `RENDER_EXTERNAL_HOSTNAME` is set for you and is added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## Deploy

`render.yaml` describes a free Render web service. Set `DATABASE_URL` to a free Neon Postgres connection string, or to a free Render Postgres connection string. The connection string from Neon should include `sslmode=require`.
