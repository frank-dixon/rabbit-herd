"""Runtime settings. Secrets and host names come from the environment."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from .email_config import default_from_email, email_settings

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


DEBUG = env_flag("DEBUG", default=False)

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-secret-key-not-for-deployment-use"
    else:
        raise ImproperlyConfigured("Set SECRET_KEY in the environment.")
# Previous keys still verify sessions and other signatures after rotation.
SECRET_KEY_FALLBACKS = env_list("SECRET_KEY_FALLBACKS")


def hostname_from_env(name):
    """Bare host from an environment variable. Scheme and path are dropped."""
    value = os.environ.get(name, "").strip()
    if "://" in value:
        value = value.split("://", 1)[1]
    return value.split("/", 1)[0].strip()


def public_hostnames():
    """Hosts that may serve the app. The first name is the passkey host.

    APP_HOSTNAME wins, then the stable Vercel production host, then Render.
    VERCEL_URL is the per-deployment host. It is allowed to answer requests,
    and it becomes the passkey host only when nothing more stable is set.
    """
    names = []
    for name in (
        "APP_HOSTNAME",
        "VERCEL_PROJECT_PRODUCTION_URL",
        "RENDER_EXTERNAL_HOSTNAME",
        "VERCEL_URL",
    ):
        cleaned = hostname_from_env(name)
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


PUBLIC_HOSTNAMES = public_hostnames()

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
for hostname in PUBLIC_HOSTNAMES:
    if hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(hostname)
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
for hostname in PUBLIC_HOSTNAMES:
    origin = f"https://{hostname}"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "anymail",
    "accounts",
    "rabbits",
    "pages",
    "e2e",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "pages.middleware.security_headers",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "rabbits.derived.middleware",
    "accounts.ratelimit.middleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "pages.middleware.prefetch_keeps_messages",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "pages.errors.branded_debug_404",
]

ROOT_URLCONF = "rabbit_herd.urls"

# With DEBUG on, 404s still show the branded page; set SHOW_DEBUG_404=1 (or add
# ?debug=1 to a URL) to see Django's technical 404 instead.
SHOW_DEBUG_404 = env_flag("SHOW_DEBUG_404", default=False)
CSRF_FAILURE_VIEW = "pages.errors.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "builtins": ["rabbits.templatetags.dates"],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pages.nav.app_nav",
                "pages.nav.app_name",
                "pages.nav.ui",
                "pages.nav.features",
                "pages.nav.guide",
            ],
        },
    },
]

# The name people see in the app, page titles and emails. The code, URLs and
# hosting services keep the rabbit-herd name.
APP_NAME = "Bramble Burrow"

# Feature flags. Locations (cages and hutches) is hidden for now; the models and data stay.
FEATURE_LOCATIONS = os.environ.get("FEATURE_LOCATIONS", "") == "1"

WSGI_APPLICATION = "rabbit_herd.wsgi.application"
ASGI_APPLICATION = "rabbit_herd.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# Dates such as "today", overdue tasks and day labels follow the keeper's zone.
TIME_ZONE = os.environ.get("TIME_ZONE", "").strip() or "America/New_York"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
# Uploaded files. Serverless hosts such as Vercel have a read-only app
# directory, so default to /tmp there; Django creates the folder on first save.
MEDIA_ROOT = Path(
    os.environ.get("MEDIA_ROOT")
    or ("/tmp/media" if os.environ.get("VERCEL") else BASE_DIR / "media")
)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

# Where uploaded photos live. PHOTO_STORAGE=s3 keeps them in a private
# S3-compatible bucket (Supabase Storage in production), because Vercel's
# /tmp is wiped between requests. Anything else uses the local folder above.
# The bucket is private. Photo URLs always go through an owner-checked view;
# with S3 that view answers with a one-hour signed link (rabbits.photo_delivery),
# so the bytes don't pass through a Django function.
PHOTO_STORAGE = os.environ.get("PHOTO_STORAGE", "").strip().lower()
if PHOTO_STORAGE == "s3":
    DEFAULT_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["PHOTO_S3_BUCKET"],
            "endpoint_url": os.environ["PHOTO_S3_ENDPOINT_URL"],
            "region_name": os.environ.get("PHOTO_S3_REGION", "us-east-1"),
            "access_key": os.environ["PHOTO_S3_ACCESS_KEY_ID"],
            "secret_key": os.environ["PHOTO_S3_SECRET_ACCESS_KEY"],
            "addressing_style": "path",
            "signature_version": "s3v4",
            "default_acl": None,
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }
else:
    DEFAULT_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
PHOTO_SIGNED_URLS = env_flag("PHOTO_SIGNED_URLS", default=PHOTO_STORAGE == "s3")
PHOTO_SIGNED_URL_SECONDS = int(os.environ.get("PHOTO_SIGNED_URL_SECONDS", "3600"))

STORAGES = {
    "default": DEFAULT_STORAGE,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "index"

WEBAUTHN_RP_NAME = os.environ.get("WEBAUTHN_RP_NAME", "").strip() or APP_NAME
WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", "").strip()
WEBAUTHN_ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "").strip()
primary_hostname = PUBLIC_HOSTNAMES[0] if PUBLIC_HOSTNAMES else ""
if not WEBAUTHN_RP_ID and primary_hostname:
    WEBAUTHN_RP_ID = primary_hostname
if not WEBAUTHN_ORIGIN and primary_hostname:
    WEBAUTHN_ORIGIN = f"https://{primary_hostname}"
if DEBUG and not WEBAUTHN_RP_ID:
    WEBAUTHN_RP_ID = "localhost"
if DEBUG and not WEBAUTHN_ORIGIN:
    WEBAUTHN_ORIGIN = "http://localhost:8000"
if not DEBUG and (not WEBAUTHN_RP_ID or not WEBAUTHN_ORIGIN):
    raise ImproperlyConfigured(
        "Set WEBAUTHN_RP_ID and WEBAUTHN_ORIGIN, or set APP_HOSTNAME, "
        "VERCEL_PROJECT_PRODUCTION_URL, RENDER_EXTERNAL_HOSTNAME, or VERCEL_URL."
    )

APP_HOSTNAME = hostname_from_env("APP_HOSTNAME")
DEFAULT_FROM_EMAIL = default_from_email(os.environ, APP_NAME)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Where people write for help or to delete their account (privacy page, terms).
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "").strip()
# EMAIL_BACKEND stays in charge. Defining MAILERS would make Django ignore it,
# including the locmem backend the tests swap in.
_email = email_settings(os.environ)
EMAIL_BACKEND = _email["EMAIL_BACKEND"]
ANYMAIL = _email.get("ANYMAIL", {})
EMAIL_HOST = _email.get("EMAIL_HOST", "")
EMAIL_PORT = _email.get("EMAIL_PORT", 587)
EMAIL_HOST_USER = _email.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _email.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _email.get("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _email.get("EMAIL_USE_SSL", False)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Default cache stays per process. Attempt limits need one shared count across
# serverless instances, so they use a database table (created by a migration).
# Genetics reads (rabbits.derived): "old" stored Gene rows only, "new" rows plus
# genes computed from the coat, "both" serves old and logs any difference.
GENETICS_READ = os.environ.get("GENETICS_READ", "new")

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "ratelimit": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "rate_limit_cache"},
}

# Who may tell us the visitor's IP for attempt limits (accounts.ratelimit.client_ip).
TRUST_VERCEL_FORWARDED = env_flag("TRUST_VERCEL_FORWARDED", default=bool(os.environ.get("VERCEL")))
TRUSTED_PROXIES = env_list("TRUSTED_PROXIES")

# Content-Security-Policy (Django's CSP middleware). No inline scripts or
# handlers anywhere in the app; inline style attributes are still allowed.
# Photos may come from the photo bucket's signed URLs (PHOTO_S3_ENDPOINT_URL).
from django.utils.csp import CSP  # noqa: E402

def _origin(url):
    from urllib.parse import urlsplit
    parts = urlsplit(url or "")
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""

_photo_origin = _origin(os.environ.get("PHOTO_S3_ENDPOINT_URL", ""))
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "blob:"] + ([_photo_origin] if _photo_origin else []),
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF] + ([_photo_origin] if _photo_origin else []),
    "manifest-src": [CSP.SELF],
    "worker-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
PERMISSIONS_POLICY = (
    "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), "
    "publickey-credentials-get=(self), publickey-credentials-create=(self)"
)
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# Django admin theme (django-unfold).
from django.urls import reverse_lazy  # noqa: E402

UNFOLD = {
    "SITE_TITLE": "Bramble Burrow",
    "SITE_HEADER": "Bramble Burrow",
    # Always light (Frank, 2026-10-16); Unfold has no "light by default, switchable" option.
    "THEME": "light",
    # Forest green scale (OKLCH), 600 is the main brand shade.
    "COLORS": {
        "primary": {
            "50": "oklch(97.5% .018 150)",
            "100": "oklch(94.5% .035 150)",
            "200": "oklch(89% .065 150)",
            "300": "oklch(81% .095 150)",
            "400": "oklch(70% .115 150)",
            "500": "oklch(59% .12 150)",
            "600": "oklch(49% .105 150)",
            "700": "oklch(42% .09 150)",
            "800": "oklch(35% .075 150)",
            "900": "oklch(29% .06 150)",
            "950": "oklch(21% .045 150)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": group,
                "separator": True,
                "items": [
                    {"title": title, "icon": icon, "link": reverse_lazy(f"admin:{model}_changelist")}
                    for title, icon, model in items
                ],
            }
            for group, items in [
                ("Herd", [
                    ("Rabbits", "pets", "rabbits_rabbit"),
                    ("Outside rabbits", "diversity_3", "rabbits_outsiderabbit"),
                    ("Breeds", "category", "rabbits_breed"),
                    ("Breed shares", "pie_chart", "rabbits_breedshare"),
                    ("Relatives", "family_history", "rabbits_relative"),
                    ("Genes", "genetics", "rabbits_gene"),
                    ("Locations", "location_on", "rabbits_location"),
                ]),
                ("Breeding", [
                    ("Pairings", "favorite", "rabbits_pairing"),
                    ("Litters", "nest_eco_leaf", "rabbits_litter"),
                    ("Litter kits", "cruelty_free", "rabbits_litterkit"),
                    ("Litter checks", "checklist", "rabbits_littercheck"),
                    ("Kit checks", "fact_check", "rabbits_kitcheck"),
                    ("Litter notes", "note", "rabbits_litternote"),
                    ("Covers", "event", "rabbits_cover"),
                    ("Breeding schedules", "calendar_month", "rabbits_breedingschedule"),
                    ("Programs", "science", "rabbits_program"),
                    ("Program breeders", "group_work", "rabbits_programbreeder"),
                    ("Pedigree entries", "account_tree", "rabbits_pedigreeentry"),
                ]),
                ("Care", [
                    ("Weights", "monitor_weight", "rabbits_weight"),
                    ("Health notes", "medical_services", "rabbits_healthnote"),
                    ("Cull notes", "content_cut", "rabbits_cullnote"),
                    ("Tasks", "task_alt", "rabbits_task"),
                ]),
                ("Records", [
                    ("Contacts", "contacts", "rabbits_contact"),
                    ("Costs", "payments", "rabbits_expense"),
                    ("Waitlist", "hourglass_top", "rabbits_waitlistentry"),
                    ("Shows", "emoji_events", "rabbits_showentry"),
                    ("Photos", "photo_library", "rabbits_rabbitphoto"),
                ]),
                ("Accounts", [
                    ("Users", "person", "accounts_user"),
                    ("Passkeys", "key", "accounts_passkeycredential"),
                    ("Groups", "group", "auth_group"),
                    ("Herd settings", "tune", "rabbits_herdsettings"),
                ]),
                ("System", [
                    ("History", "history", "rabbits_historyentry"),
                    ("Sync ops", "sync", "rabbits_syncop"),
                    ("Admin log", "receipt_long", "admin_logentry"),
                ]),
            ]
        ],
    },
}
