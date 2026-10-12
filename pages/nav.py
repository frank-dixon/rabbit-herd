"""The app shell's menu: a side menu on tablet and desktop, bottom tabs on
phones. Only built sections are listed; nothing points at work not done yet."""

from django.urls import reverse

# Outline icons, 24x24, drawn with currentColor (no new colors).
ICONS = {
    "home": "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    "rabbits": "M4 5h16M4 12h16M4 19h16",
    "add": "M12 5v14M5 12h14",
    "archived": "M3 5h18v4H3zM5 9v10h14V9M10 13h4",
    "contacts": "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20a6 6 0 0 1 12 0M16 11a3 3 0 1 0 0-6M18 20h4a6 6 0 0 0-5-5.9",
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
        ("archived", "Archived", reverse("rabbit_list") + "?tab=archived"),
        ("contacts", "Contacts", reverse("contact_list")),
        ("account", "Account", reverse("account")),
    ]
    return {
        "app_nav": [
            {"key": key, "label": label, "short": "Add" if key == "add" else label,
             "url": url, "icon": ICONS[key], "active": key == current}
            for key, label, url in items
        ]
    }
