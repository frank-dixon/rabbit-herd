"""The app shell: bottom tabs on phones, a side menu on tablet and desktop,
and a slide-in drawer on phones (menu button, top left) with the same
sections. Only built sections are listed."""

from django.conf import settings
from django.urls import reverse


# Swatches shown in the Settings theme picker: (accent, secondary, canvas).
THEME_SWATCHES = {
    "c1": ("#0F5E63", "#D65A3E", "#F5F6F5"),
    "c2": ("#2347B5", "#E0A019", "#F5F5F3"),
    "c3": ("#22573B", "#B9582F", "#F5F4F0"),
    "c4": ("#5E2B62", "#6E8F68", "#F6F5F4"),
    "c5": ("#B3261E", "#44576C", "#F6F5F4"),
    "d1": ("#3A5070", "#8A94A0", "#EAEAEA"),
    "d2": ("#4F5A36", "#9A8F6E", "#EAEAEA"),
    "d3": ("#2F5B5B", "#8A7F72", "#DEDEDC"),
    "d4": ("#7A3F2A", "#5F6E78", "#DEDEDC"),
    "d5": ("#5A3E2B", "#8B7B5E", "#E8DCC8"),
    "d6": ("#43573D", "#9A6B4C", "#E8DCC8"),
}
# Browser chrome color per theme: (light canvas, dark canvas).
THEME_COLOR = {'c1': ('#F5F6F5', '#121717'), 'c2': ('#F5F5F3', '#121318'), 'c3': ('#F5F4F0', '#131613'), 'c4': ('#F6F5F4', '#161317'), 'c5': ('#F6F5F4', '#151515'), 'd1': ('#EAEAEA', '#1F1F1F'), 'd2': ('#EAEAEA', '#1F1F1F'), 'd3': ('#DEDEDC', '#26282A'), 'd4': ('#DEDEDC', '#26282A'), 'd5': ('#E8DCC8', '#221E19'), 'd6': ('#E8DCC8', '#221E19')}


def ui(request):
    """The signed-in user's theme and grid density, rendered onto <html> so
    the page paints in the right colors with no flash and no JS."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        theme, density, mode = user.ui_theme or "c1", user.ui_density or "roomy", user.ui_mode or "system"
    else:
        theme, density, mode = "c1", "roomy", "system"
    return {"ui_theme": theme, "ui_density": density, "ui_mode": mode, "ui_icons": ICONS, "ui_theme_color": THEME_COLOR.get(theme, THEME_COLOR["c1"])[0],
            "ui_theme_color_dark": THEME_COLOR.get(theme, THEME_COLOR["c1"])[1]}


def app_name(request):
    """The user-facing app name, from settings.APP_NAME."""
    return {"app_name": settings.APP_NAME}

# Outline icons, 24x24, drawn with currentColor.
ICONS = {
    "today": "M4 6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5zM4 10h16M8 3v4M16 3v4M9 14.5l2 2 4-4",
    "home": "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    "rabbits": "M9.5 9C8 9 7 7 7 4.8 7 3.6 7.6 3 8.3 3c1.3 0 2.2 2.6 2.2 4.6M14.5 9c1.5 0 2.5-2 2.5-4.2C17 3.6 16.4 3 15.7 3c-1.3 0-2.2 2.6-2.2 4.6M6 15a6 6 0 0 1 12 0c0 3.3-2.7 6-6 6s-6-2.7-6-6zM10 15h.01M14 15h.01",
    "add": "M12 5v14M5 12h14",
    "archived": "M3 5h18v4H3zM5 9v10h14V9M10 13h4",
    "contacts": "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20a6 6 0 0 1 12 0M16 11a3 3 0 1 0 0-6M18 20h4a6 6 0 0 0-5-5.9",
    "locations": "M4 4h16v16H4zM4 12h16M12 4v16",
    "pairings": "M8 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM16 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    "litters": "M7 4v3M17 4v3M4 8h16v12H4zM8 12h3v3H8z",
    "weights": "M12 4v16M7 20h10M5 8h14M5 8l-3 6a3 3 0 0 0 6 0zM19 8l-3 6a3 3 0 0 0 6 0zM12 4a1 1 0 1 0 0 .01",
    "tasks": "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
    "health": "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10zM9 11h6M12 8v6",
    "shows": "M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 21h8M9 17h6v4H9z",
    "costs": "M12 3v18M16.5 7.5c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 2 2.6 4.5 3 4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3",
    "waitlist": "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
    "export": "M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14",
    "glossary": "M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5zM20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5zM7 8h1.5M7 11h1.5M15.5 8H17M15.5 11H17",
    "settings": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
    "account": "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "photos": "M4 8a2 2 0 0 1 2-2h2l1.5-2h5L16 6h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
}

# Every place the bottom bar can point at: key -> (label, url name, query).
DESTINATIONS = {
    "today": ("Today", "index", ""),
    "rabbits": ("Rabbits", "rabbit_list", ""),
    "litters": ("Litters", "litter_list", ""),
    "weights": ("Weights", "weights_hub", ""),
    "tasks": ("Tasks", "task_list", ""),
    "pairings": ("Pairings", "pairing_list", ""),
    "health": ("Health", "health_list", ""),
    "shows": ("Shows", "show_list", ""),
    "locations": ("Locations", "location_list", ""),
    "costs": ("Costs", "cost_list", ""),
    "waitlist": ("Waitlist", "waitlist", ""),
    "contacts": ("Contacts", "contact_list", ""),
    "glossary": ("Glossary", "glossary", ""),
    "settings": ("Settings", "account", ""),
}
# Settings lives behind the gear (side menu, drawer and account panel), so it is never a tab.
TAB_CHOICES = [key for key in DESTINATIONS if key != "settings"]


def feature_off(key):
    """Destinations hidden by a feature flag (settings.FEATURE_LOCATIONS)."""
    from django.conf import settings as conf

    return key == "locations" and not getattr(conf, "FEATURE_LOCATIONS", False)


def tab_choices():
    return [key for key in TAB_CHOICES if not feature_off(key)]


def features(request):
    from django.conf import settings as conf

    return {"feature_locations": getattr(conf, "FEATURE_LOCATIONS", False)}

DEFAULT_TABS = ["today", "rabbits", "litters", "weights", "tasks"]
MIN_TABS, MAX_TABS = 3, 5

# Side menu (tablet and desktop) and the phone drawer: the everyday sections, then Records.
RAIL = ["today", "rabbits", "litters", "pairings", "weights", "tasks", "locations", "archived"]
RECORDS = ["contacts", "costs", "waitlist", "shows", "health", "export", "glossary"]
# The account popover from the footer gear.
PANEL = ["settings", "account"]

PREFIXES = [
    ("/rabbits/new/", "add"), ("/rabbits/archived/", "archived"), ("/rabbits/", "rabbits"),
    ("/locations/", "locations"), ("/tasks/", "tasks"), ("/pairings/", "pairings"), ("/litters/", "litters"),
    ("/weights/", "weights"), ("/health/", "health"), ("/shows/", "shows"), ("/waitlist/", "waitlist"),
    ("/costs/", "costs"), ("/contacts/", "contacts"), ("/settings/", "settings"), ("/account/", "settings"),
    ("/accounts/password", "settings"), ("/glossary/", "glossary"),
]


def active_key(request):
    path = request.path
    if path == "/":
        return "today"
    if path == "/rabbits/" and request.GET.get("tab") == "archived":
        return "archived"
    for prefix, key in PREFIXES:
        if path.startswith(prefix):
            return key
    return ""


def clean_tabs(keys):
    """A valid bar: known destinations, no repeats, 3 to 5 of them."""
    choices = tab_choices()
    seen = []
    for key in keys or []:
        if key in choices and key not in seen:
            seen.append(key)
    seen = seen[:MAX_TABS]
    if not keys or not seen:
        return list(DEFAULT_TABS)
    # A saved bar that lost a hidden page keeps the rest, topped up from the defaults.
    for key in DEFAULT_TABS:
        if len(seen) >= MIN_TABS:
            break
        if key not in seen:
            seen.append(key)
    return seen


def due_count(user):
    from rabbits.tasks import open_items

    from django.utils import timezone

    today = timezone.localdate()
    return sum(1 for item in open_items(user, today) if item["date"] <= today)


def item(key, current, label=None, url=None):
    if url is None:
        name, query = {
            "add": ("rabbit_create", ""), "archived": ("rabbit_list", "?tab=archived"),
            "export": ("account", "#export"), "account": ("account", "#account"),
        }.get(key, DESTINATIONS.get(key, ("", "", ""))[1:])
        url = reverse(name) + query
    label = label or {"add": "Add a rabbit", "archived": "Archived", "export": "Export", "account": "Account"}.get(key) or DESTINATIONS[key][0]
    return {"key": key, "label": label, "short": "Add" if key == "add" else label, "url": url,
            "icon": ICONS[key], "active": key == current}


def app_nav(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    current = active_key(request)
    tabs = clean_tabs(getattr(user, "tab_bar", None))
    nav_items = [item(key, current) for key in RAIL if not feature_off(key)]
    tab_items = [item(key, current) for key in tabs]
    if "tasks" in tabs:
        due = due_count(user)
        for entry in tab_items:
            if entry["key"] == "tasks":
                entry["badge"] = due
    return {
        "app_nav": nav_items,
        "app_tabs": tab_items,
        "app_records": [item(key, current) for key in RECORDS],
        "app_panel": [item(key, current) for key in PANEL],
        "app_destinations": [item(key, current) for key in tab_choices()],
        "app_settings_icon": ICONS["settings"],
        "herd_prefs_name": herd_name(user),
        "account_name": herd_name(user) or user.get_full_name() or user.email,
        "account_detail": account_detail(user),
    }


def herd_name(user):
    from rabbits.models import prefs

    return (prefs(user).rabbitry_name or "").strip()


def account_detail(user):
    """The second footer line: the person's name under a rabbitry name, else their email."""
    full = user.get_full_name()
    if herd_name(user) and full:
        return full
    return user.email if (herd_name(user) or full) else ""
