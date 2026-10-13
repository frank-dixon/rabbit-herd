"""The app shell's menu: a side menu on tablet and desktop, bottom tabs on
phones. Only built sections are listed; nothing points at work not done yet."""

from django.conf import settings
from django.urls import reverse


def app_name(request):
    """The user-facing app name, from settings.APP_NAME."""
    return {"app_name": settings.APP_NAME}

# Outline icons, 24x24, drawn with currentColor (no new colors).
ICONS = {
    "home": "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    "rabbits": "M4 5h16M4 12h16M4 19h16",
    "add": "M12 5v14M5 12h14",
    "archived": "M3 5h18v4H3zM5 9v10h14V9M10 13h4",
    "contacts": "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20a6 6 0 0 1 12 0M16 11a3 3 0 1 0 0-6M18 20h4a6 6 0 0 0-5-5.9",
    "locations": "M4 4h16v16H4zM4 12h16M12 4v16",
    "pairings": "M8 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM16 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    "litters": "M7 4v3M17 4v3M4 8h16v12H4zM8 12h3v3H8z",
    "tasks": "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
    "more": "M5 12h.01M12 12h.01M19 12h.01",
    "account": "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
}


def active_key(request):
    path = request.path
    if path == "/":
        return "home"
    if path.startswith("/rabbits/new/"):
        return "add"
    if path.startswith("/rabbits/archived/") or (path == "/rabbits/" and request.GET.get("tab") == "archived"):
        return "archived"
    if path.startswith("/rabbits/"):
        return "rabbits"
    if path.startswith("/locations/"):
        return "locations"
    if path.startswith("/tasks/"):
        return "tasks"
    if path.startswith("/pairings/"):
        return "pairings"
    if path.startswith("/litters/"):
        return "litters"
    if path.startswith("/contacts/"):
        return "contacts"
    if path.startswith("/account/") or path.startswith("/accounts/password"):
        return "account"
    return ""


def app_nav(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    current = active_key(request)
    items = [
        ("home", "Home", reverse("index")),
        ("rabbits", "Rabbits", reverse("rabbit_list")),
        ("add", "Add a rabbit", reverse("rabbit_create")),
        ("tasks", "Tasks", reverse("task_list")),
        ("archived", "Archived", reverse("rabbit_list") + "?tab=archived"),
        ("locations", "Locations", reverse("location_list")),
        ("pairings", "Pairings", reverse("pairing_list")),
        ("litters", "Litters", reverse("litter_list")),
        ("contacts", "Contacts", reverse("contact_list")),
        ("account", "Account", reverse("account")),
    ]
    # Phones get four tabs; everything else sits under More (the account page).
    phone = {"home", "rabbits", "add"}
    more_active = current not in phone and current != ""
    return {
        "app_tabs": [
            {"key": key, "label": label, "short": "Add" if key == "add" else label, "url": url,
             "icon": ICONS[key], "active": key == current}
            for key, label, url in items if key in phone
        ] + [{"key": "more", "label": "More", "short": "More", "url": reverse("account"), "icon": ICONS["more"], "active": more_active}],
        "app_more": [
            {"key": key, "label": label, "url": url, "icon": ICONS[key], "active": key == current}
            for key, label, url in items if key not in phone and key != "account"
        ],
        "app_nav": [
            {"key": key, "label": label, "short": "Add" if key == "add" else label,
             "url": url, "icon": ICONS[key], "active": key == current}
            for key, label, url in items
        ]
    }
