"""Choose the outgoing mail backend from environment variables."""

from django.core.exceptions import ImproperlyConfigured

CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
RESEND_BACKEND = "anymail.backends.resend.EmailBackend"


def _flag(environ, name, default):
    raw = environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def email_settings(environ):
    """Return the Django email settings for this environment.

    EMAIL_PROVIDER=resend uses Resend's HTTPS API. EMAIL_PROVIDER=smtp, or an
    unset provider with EMAIL_HOST, uses SMTP. Anything else prints to the
    console. Defining MAILERS is intentionally avoided: Django would then
    ignore EMAIL_BACKEND, including the locmem backend used in tests.
    """
    provider = environ.get("EMAIL_PROVIDER", "").strip().lower()
    host = environ.get("EMAIL_HOST", "").strip()
    if provider == "resend":
        api_key = environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "Set RESEND_API_KEY when EMAIL_PROVIDER is resend."
            )
        if not environ.get("DEFAULT_FROM_EMAIL", "").strip():
            raise ImproperlyConfigured(
                "Set DEFAULT_FROM_EMAIL when EMAIL_PROVIDER is resend."
            )
        return {
            "EMAIL_BACKEND": RESEND_BACKEND,
            "ANYMAIL": {"RESEND_API_KEY": api_key},
        }
    if provider not in {"", "console", "smtp"}:
        raise ImproperlyConfigured(
            "EMAIL_PROVIDER must be resend, smtp, or console."
        )
    if provider == "smtp" or (not provider and host):
        if not host:
            raise ImproperlyConfigured("Set EMAIL_HOST when EMAIL_PROVIDER is smtp.")
        port_raw = environ.get("EMAIL_PORT", "").strip() or "587"
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ImproperlyConfigured("EMAIL_PORT must be an integer.") from exc
        return {
            "EMAIL_BACKEND": SMTP_BACKEND,
            "EMAIL_HOST": host,
            "EMAIL_PORT": port,
            "EMAIL_HOST_USER": environ.get("EMAIL_HOST_USER", ""),
            "EMAIL_HOST_PASSWORD": environ.get("EMAIL_HOST_PASSWORD", ""),
            "EMAIL_USE_TLS": _flag(environ, "EMAIL_USE_TLS", True),
            "EMAIL_USE_SSL": _flag(environ, "EMAIL_USE_SSL", False),
        }
    return {"EMAIL_BACKEND": CONSOLE_BACKEND}
