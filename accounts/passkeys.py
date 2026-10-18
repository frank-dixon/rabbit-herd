"""WebAuthn registration and authentication ceremonies."""

import binascii
import json

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
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .models import PasskeyCredential

REGISTER_CHALLENGE = "webauthn_register_challenge"
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
    # Platform only. With no attachment, Safari also builds a security-key
    # request and puts residentKey on that request alone, so iOS offers a
    # physical key or a QR code for another device instead of Face ID.
    return AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment.PLATFORM,
        resident_key=ResidentKeyRequirement.REQUIRED,
        user_verification=UserVerificationRequirement.REQUIRED,
    )


def registration_options(request, payload):
    """Passkeys are an add-on to a signed-in account with an email and
    password; there is no passkey-only signup."""
    if not request.user.is_authenticated:
        raise PasskeyError("Sign in first, then add a passkey.", status=403)
    user = request.user
    if user.is_guest or user.is_demo:
        raise PasskeyError("Create an account first, then add a passkey.", status=403)
    user_id = bytes(user.webauthn_user_handle)
    user_name = user.email
    exclude = [
        PublicKeyCredentialDescriptor(id=bytes(cred.credential_id))
        for cred in user.passkeys.all()
    ]

    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id,
        user_name=user_name,
        user_display_name=user_name,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=_selection(),
        exclude_credentials=exclude or None,
        # ES256, then RS256. EdDSA (-8) is not a key iCloud Keychain can
        # create, and it is the algorithm py_webauthn offers first.
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    request.session[REGISTER_CHALLENGE] = bytes_to_base64url(options.challenge)
    return options_to_json_dict(options)


def verify_registration(request, credential):
    challenge = request.session.pop(REGISTER_CHALLENGE, None)
    if not challenge:
        raise PasskeyError("That passkey registration expired. Start again.")
    if not request.user.is_authenticated or request.user.is_guest or request.user.is_demo:
        raise PasskeyError("Sign in first, then add a passkey.", status=403)

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

    user = request.user
    with transaction.atomic():
        try:
            PasskeyCredential.objects.create(
                user=user,
                credential_id=verification.credential_id,
                public_key=verification.credential_public_key,
                sign_count=verification.sign_count,
            )
        except IntegrityError as exc:
            raise PasskeyError("That passkey is already registered.") from exc
        if user.passkey_offer != "done":
            user.passkey_offer = "done"
            user.save(update_fields=["passkey_offer"])
    return user, False


def authentication_options(request):
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    request.session[AUTH_CHALLENGE] = bytes_to_base64url(options.challenge)
    payload = options_to_json_dict(options)
    # py_webauthn emits allowCredentials: [] for a discoverable ceremony.
    # Some clients treat that empty list as "no credential is allowed"
    # and fall through to a security key. Omit it.
    if not payload.get("allowCredentials"):
        payload.pop("allowCredentials", None)
    return payload


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
