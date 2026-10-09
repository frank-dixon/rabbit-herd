# Rabbit Herd

Rabbit Herd is a private record keeper for a small rabbitry. Sign in with a passkey (Face ID, a fingerprint, or a device PIN) or with your email and password. You can also look around as a guest. A new account confirms its email before it can sign in. You can change your password, or reset it if you forget it.

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build
cp .env.example .env
```

Edit `.env`. Leave `DATABASE_URL` empty to use a local SQLite file, or set it to a Postgres connection string. Then:

```bash
python manage.py migrate
python manage.py ensure_demo_user
python manage.py runserver
```

`npm run watch` rebuilds the stylesheet and script while you work. Open http://localhost:8000.

With the sample demo values, sign in as `demo@example.com` after you set `DEMO_PASSWORD`. Confirmation and password-reset mail prints in the terminal unless you set `EMAIL_HOST`.

## Environment variables

| Variable | Purpose |
|---|---|
| `DEBUG` | `true` for local development. Leave unset, or set `false`, on the host. |
| `SECRET_KEY` | Long random string. Required when `DEBUG` is off. |
| `DATABASE_URL` | Postgres connection string. SQLite is used only when this is unset. |
| `ALLOWED_HOSTS` | Comma-separated host names. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, including the scheme. |
| `WEBAUTHN_RP_ID` | Passkey domain, with no scheme and no port. `localhost` locally. |
| `WEBAUTHN_RP_NAME` | Name the browser shows when it asks for a passkey. |
| `WEBAUTHN_ORIGIN` | Origin you open in the browser, such as `http://localhost:8000`. |
| `DEMO_EMAIL` | Email for the ready-to-use demo account. |
| `DEMO_PASSWORD` | Password for that demo account. |
| `DEFAULT_FROM_EMAIL` | Address confirmation and reset mail is sent from. |
| `EMAIL_HOST` | SMTP server. Unset means mail is printed to the console. |
| `EMAIL_PORT` | SMTP port. Defaults to `587`. |
| `EMAIL_HOST_USER` | SMTP username. |
| `EMAIL_HOST_PASSWORD` | SMTP password. |
| `EMAIL_USE_TLS` | `true` or `false`. Defaults to `true` when `EMAIL_HOST` is set. |
| `EMAIL_USE_SSL` | `true` or `false`. Defaults to `false`. |

`python manage.py ensure_demo_user` reads `DEMO_EMAIL` and `DEMO_PASSWORD`, creates that account if needed, and marks the email confirmed. Run it again whenever you want; it updates the same account. If either variable is missing, it leaves the database alone.

## Deploy on Render

`render.yaml` is a free web service. Create a free Postgres database on Neon or on Render, and set `DATABASE_URL` to its connection string when Render asks. A Neon string should include `sslmode=require`.

Set these on the service:

- `SECRET_KEY` (the blueprint can generate one)
- `DATABASE_URL`
- `DEMO_EMAIL`
- `DEMO_PASSWORD`
- `DEBUG` = `false`

Render sets `RENDER_EXTERNAL_HOSTNAME` for you. That host is added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, and it is used as the passkey relying party id and origin when `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` are left unset.

Set `EMAIL_HOST` and the other SMTP variables when you want confirmation mail delivered. Until then, those messages are written to the service logs.
