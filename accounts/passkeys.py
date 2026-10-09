"""WebAuthn registration and authentication ceremonies."""

import binascii
import json
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import PasskeyCredential, User

REGISTER_CHALLENGE = "webauthn_register_challenge"
REGISTER_EMAIL = "webauthn_register_email"
REGISTER_HANDLE = "webauthn_register_handle"
AUTH_CHALLENGE = "webauthn_auth_challenge"


class PasskeyError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def read_json(request):
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PasskeyError("The request was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise PasskeyError("The request was not a JSON object.")
    return payload


def _selection():
    return AuthenticatorSelectionCriteria(
        resident_key=ResidentKeyRequirement.REQUIRED,
        user_verification=UserVerificationRequirement.REQUIRED,
    )


def registration_options(request, payload):
    if request.user.is_authenticated:
        user = request.user
        user_id = bytes(user.webauthn_user_handle)
        if user.is_guest:
            raise PasskeyError("Guest sessions cannot register a passkey.")
        user_name = user.email
        exclude = [
            PublicKeyCredentialDescriptor(id=bytes(cred.credential_id))
            for cred in user.passkeys.all()
        ]
        request.session.pop(REGISTER_EMAIL, None)
        request.session.pop(REGISTER_HANDLE, None)
    else:
        email = str(payload.get("email") or "").strip().lower()
        if not email or "@" not in email:
            raise PasskeyError("Enter the email address for this passkey.")
        if User.objects.filter(email__iexact=email).exists():
            raise PasskeyError("An account with that email already exists.")
        user_id = secrets_token()
        user_name = email
        exclude = []
        request.session[REGISTER_EMAIL] = email
        request.session[REGISTER_HANDLE] = bytes_to_base64url(user_id)

    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id,
        user_name=user_name,
        user_display_name=user_name,
        authenticator_selection=_selection(),
        exclude_credentials=exclude or None,
    )
    request.session[REGISTER_CHALLENGE] = bytes_to_base64url(options.challenge)
    return options_to_json_dict(options)


def secrets_token():
    return secrets.token_bytes(32)


def verify_registration(request, credential):
    challenge = request.session.pop(REGISTER_CHALLENGE, None)
    email = request.session.pop(REGISTER_EMAIL, None)
    handle = request.session.pop(REGISTER_HANDLE, None)
    if not challenge:
        raise PasskeyError("That passkey registration expired. Start again.")

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise PasskeyError("The passkey could not be verified.") from exc

    with transaction.atomic():
        created = False
        if request.user.is_authenticated:
            user = request.user
        else:
            if not email or not handle:
                raise PasskeyError("That passkey registration expired. Start again.")
            user = User(
                email=email,
                webauthn_user_handle=base64url_to_bytes(handle),
                is_active=False,
                email_confirmed=False,
            )
            user.set_unusable_password()
            try:
                user.save()
            except IntegrityError as exc:
                raise PasskeyError("An account with that email already exists.") from exc
            created = True
        try:
            PasskeyCredential.objects.create(
                user=user,
                credential_id=verification.credential_id,
                public_key=verification.credential_public_key,
                sign_count=verification.sign_count,
            )
        except IntegrityError as exc:
            raise PasskeyError("That passkey is already registered.") from exc
    return user, created


def authentication_options(request):
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    request.session[AUTH_CHALLENGE] = bytes_to_base64url(options.challenge)
    return options_to_json_dict(options)


def verify_authentication(request, credential):
    challenge = request.session.pop(AUTH_CHALLENGE, None)
    if not challenge:
        raise PasskeyError("That passkey sign-in expired. Start again.")

    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        raise PasskeyError("The passkey response was incomplete.")
    try:
        credential_id = base64url_to_bytes(raw_id)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise PasskeyError("The passkey response was incomplete.") from exc

    stored = (
        PasskeyCredential.objects.select_related("user")
        .filter(credential_id=credential_id)
        .first()
    )
    if stored is None:
        raise PasskeyError("No account is registered for that passkey.")

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise PasskeyError("The passkey could not be verified.") from exc

    user_handle = (credential.get("response") or {}).get("userHandle")
    if user_handle:
        try:
            presented = base64url_to_bytes(user_handle)
        except (binascii.Error, TypeError, ValueError) as exc:
            raise PasskeyError("The passkey could not be verified.") from exc
        if presented != bytes(stored.user.webauthn_user_handle):
            raise PasskeyError("The passkey could not be verified.")

    if not stored.user.is_active or not stored.user.email_confirmed:
        raise PasskeyError("Confirm your email before signing in.")

    stored.sign_count = verification.new_sign_count
    stored.save(update_fields=["sign_count"])
    return stored.user
