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


RESEND_TEST_SENDER = "onboarding@resend.dev"  # Resend's shared sender; delivers only to the account owner's address


def default_from_email(environ, app_name):
    """DEFAULT_FROM_EMAIL if set; with Resend and no own domain yet, Resend's
    onboarding sender (test only); otherwise a harmless localhost address."""
    configured = environ.get("DEFAULT_FROM_EMAIL", "").strip()
    if configured:
        return configured
    if email_settings(environ)["EMAIL_BACKEND"] == RESEND_BACKEND:
        return f"{app_name} <{RESEND_TEST_SENDER}>"
    return f"{app_name} <noreply@localhost>"


def email_settings(environ):
    """Return the Django email settings for this environment.

    EMAIL_PROVIDER=resend uses Resend's HTTPS API. EMAIL_PROVIDER=smtp, or an
    unset provider with EMAIL_HOST, uses SMTP. Anything else prints to the
    console. Defining MAILERS is intentionally avoided: Django would then
    ignore EMAIL_BACKEND, including the locmem backend used in tests.
    """
    provider = environ.get("EMAIL_PROVIDER", "").strip().lower()
    host = environ.get("EMAIL_HOST", "").strip()
    if not provider and environ.get("RESEND_API_KEY", "").strip():
        provider = "resend"  # a Resend key alone is enough to send through Resend
    if provider == "resend":
        api_key = environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "Set RESEND_API_KEY when EMAIL_PROVIDER is resend."
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
