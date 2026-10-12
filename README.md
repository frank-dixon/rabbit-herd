# Rabbit Herd

Rabbit Herd is a private record keeper for a small rabbitry. Sign in with a passkey (Face ID, a fingerprint, or a device PIN) or with your email and password. You can also look around as a guest. A new account confirms its email before it can sign in. You can change your password, or reset it if you forget it.

Signed in, you keep your own rabbits. A rabbit has a name or ear tag, a sex of doe or buck, a breed, a color, a birth date, optional photos, and a status of breeding, growing out, sold, or culled. Archiving takes a rabbit off the active list and keeps the record. You can restore an archived rabbit. You only see your own.

Photos are stored as `RabbitPhoto` rows, one of which can be the rabbit's main photo. They have no public URL: each one is served to its owner only, at `/rabbits/photos/<id>/`. A rabbit's Photos page (`/rabbits/<id>/photos/`) takes JPEG, PNG or WebP uploads up to 10 MB, each with optional notes. Every upload is re-saved with Pillow, which drops EXIF data such as GPS location, and stored under a random name.

"Add a rabbit" (`/rabbits/new/`) asks one question per card, built for phones: name or ear tag, doe or buck, birth date, status, purebred or crossbred, the breed, its color, and any known relatives, then a review. A purebred rabbit takes one breed from a catalog of 86 (53 ARBA and 33 British Rabbit Council breeds). A crossbred rabbit lists two or more breeds whose shares total exactly 100%. The color card offers the breed's recognized colors (a single color is chosen already), with Another color for anything else; crossbreds and breeds recognized in many colors describe the color instead. Relatives can be rabbits in your herd or outside rabbits, with one dam (a doe) and one sire (a buck) at most. Answers are kept in your session as you go, so a refresh or Back keeps them, and every card works without JavaScript.

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

Run the tests with `python manage.py test` and `npm run test:js`.

With the sample demo values, sign in as `demo@example.com` after you set `DEMO_PASSWORD`. Confirmation and password-reset mail prints in the terminal unless you set `EMAIL_PROVIDER` or `EMAIL_HOST`.

## Environment variables

| Variable | Purpose |
|---|---|
| `DEBUG` | `true` for local development. Leave unset, or set `false`, on the host. |
| `SECRET_KEY` | Long random string. Required when `DEBUG` is off. |
| `SECRET_KEY_FALLBACKS` | Comma-separated previous secret keys. Set these when rotating `SECRET_KEY` so existing sessions keep working. |
| `DATABASE_URL` | Postgres connection string. SQLite is used only when this is unset. |
| `ALLOWED_HOSTS` | Comma-separated host names. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins, including the scheme. |
| `APP_HOSTNAME` | Stable public host, with no scheme and no port. When it is set, passkeys and account email links use it. It is also added to allowed hosts and CSRF origins. |
| `VERCEL_PROJECT_PRODUCTION_URL` | Set by Vercel. The stable production host, with no scheme. Passkeys use it when `APP_HOSTNAME` is unset. |
| `VERCEL_URL` | Set by Vercel. This deployment's host, with no scheme. It can serve that deployment. Passkeys use it only when no stable host is set. |
| `RENDER_EXTERNAL_HOSTNAME` | Set by Render. Added to allowed hosts and CSRF origins, and used for passkeys when no stable host above is set. |
| `WEBAUTHN_RP_ID` | Passkey domain, with no scheme and no port. `localhost` locally. |
| `WEBAUTHN_RP_NAME` | Name the browser shows when it asks for a passkey. |
| `WEBAUTHN_ORIGIN` | Origin you open in the browser, such as `http://localhost:8000`. |
| `DEMO_EMAIL` | Email for the ready-to-use demo account. |
| `DEMO_PASSWORD` | Password for that demo account. |
| `DEFAULT_FROM_EMAIL` | Address confirmation and reset mail is sent from. Required when `EMAIL_PROVIDER` is `resend`. |
| `EMAIL_PROVIDER` | `resend`, `smtp`, or `console`. Unset uses SMTP when `EMAIL_HOST` is set, and the console otherwise. |
| `RESEND_API_KEY` | API key for Resend. Required when `EMAIL_PROVIDER` is `resend`. Sending access is enough. |
| `EMAIL_HOST` | SMTP server. Used when `EMAIL_PROVIDER` is `smtp`, or when `EMAIL_PROVIDER` is unset and this is set. |
| `EMAIL_PORT` | SMTP port. Defaults to `587`. |
| `EMAIL_HOST_USER` | SMTP username. |
| `EMAIL_HOST_PASSWORD` | SMTP password. |
| `EMAIL_USE_TLS` | `true` or `false`. Defaults to `true` when `EMAIL_HOST` is set. |
| `EMAIL_USE_SSL` | `true` or `false`. Defaults to `false`. |

`python manage.py ensure_demo_user` reads `DEMO_EMAIL` and `DEMO_PASSWORD`, creates that account if needed, and marks the email confirmed. Run it again whenever you want; it updates the same account. If either variable is missing, it leaves the database alone.

## Deploy

The app runs on Vercel's free Hobby plan. Create a free Postgres database on Neon and set `DATABASE_URL` to that connection string. A Neon string should include `sslmode=require`.

Import this repository as a Django project. Leave the install command on its default, which installs `requirements.txt`. The build command is `sh vercel-build.sh`. It compiles the stylesheet and minifies the script. Vercel then collects static files and serves them from its CDN. Leave access to System Environment Variables enabled so the build can see `VERCEL_ENV`, `VERCEL_URL`, and `VERCEL_PROJECT_PRODUCTION_URL`.

Set these on the project:

- `SECRET_KEY`
- `DATABASE_URL`
- `DEBUG` = `false`
- `DEMO_EMAIL`
- `DEMO_PASSWORD`
- `APP_HOSTNAME` = the stable production host, with no scheme and no port
- `EMAIL_PROVIDER` = `resend`
- `RESEND_API_KEY` = a Resend API key with sending access
- `DEFAULT_FROM_EMAIL` = `Rabbit Herd <onboarding@resend.dev>` until a domain is verified, then an address on that domain

`APP_HOSTNAME` is the passkey host, and confirmation and password-reset links use `https://` plus that host. Use the custom domain, or the production `*.vercel.app` name, so a passkey is not tied to a one-off deployment URL. When `APP_HOSTNAME` is unset, passkeys use `VERCEL_PROJECT_PRODUCTION_URL`, and those email links use the host of the request instead.

Resend's free plan sends over HTTPS. With `onboarding@resend.dev`, Resend delivers only to the email address on the Resend account. An account created with `fdixon7@gmail.com` can receive testing mail at that address before a domain is verified. A confirmation or reset for any other address cannot, until a domain you control is verified in Resend and `DEFAULT_FROM_EMAIL` uses that domain. `rabbit-herd.vercel.app` cannot be verified, because its DNS is not yours. SMTP still works if you set `EMAIL_PROVIDER` to `smtp` and `EMAIL_HOST`. With neither Resend nor SMTP configured, messages are written to the logs.

A production deploy, where `VERCEL_ENV` is `production`, runs `python manage.py migrate --noinput` and then `python manage.py ensure_demo_user` against `DATABASE_URL`. A failed migration fails the build. Preview builds leave the database alone. Handling a request does not migrate.

## Run the container

```bash
docker build -t rabbit-herd .
docker run --env-file .env -p 8000:8000 rabbit-herd
```

Set the same variables as on Vercel, including `APP_HOSTNAME` when the platform does not provide a host name. The container listens on `PORT`, or 8000 when `PORT` is unset.

Set `EMAIL_PROVIDER` to `resend` and set `RESEND_API_KEY`, or set `EMAIL_HOST` and the other SMTP variables, when you want confirmation mail delivered. Until then, those messages are written to the service logs.
