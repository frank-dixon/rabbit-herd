"""Wording that lives in one place so it can be changed without touching templates."""

# The one-line bottom rail on guest and demo sessions (components/temp_rail.html).
RAIL = {
    "guest": {"text": "Your herd isn't saved yet.", "action": "Create free account"},
    "demo": {"text": "This is a sample herd. It can't be saved.", "action": "Start my own herd"},
}

# The one-time offer after signup (components/passkey_offer.html).
PASSKEY_OFFER = {"text": "Sign in faster next time with a passkey?", "add": "Add passkey", "skip": "Skip"}
