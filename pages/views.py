import datetime

from django.conf import settings
from django.utils import timezone
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .nav import THEME_SWATCHES

from .forms import ComponentExampleForm


def index(request):
    if request.user.is_authenticated:
        return render(request, "home.html", home_context(request.user))
    return render(request, "landing.html")


def theme_dark_swatch(key):
    """(accent, secondary, canvas) of a theme in dark mode, read from themes.css."""
    import re
    from pathlib import Path

    css = getattr(theme_dark_swatch, "_css", None)
    if css is None:
        css = theme_dark_swatch._css = (Path(settings.BASE_DIR) / "assets" / "themes.css").read_text()
    match = re.search(r'html\[data-mode="dark"\]\[data-theme="' + key + r'"\][^{]*\{(.*?)\}', css, re.S)
    if not match:
        return THEME_SWATCHES[key]
    values = dict(re.findall(r"--([a-z-]+):\s*([^;]+);", match.group(1)))
    return (values.get("accent", ""), values.get("second", ""), values.get("canvas", ""))



# Settings sections in page order: (group, anchor, label, template). The sub-nav and the page
# both render from this one list, so the links always match the order of the sections.
SETTINGS_SECTIONS = [
    ("Rabbitry", "rabbitry", "General", "pages/settings/_herd.html"),
    ("Rabbitry", "units", "Units", "pages/settings/_herd.html"),
    ("Rabbitry", "schedule", "Breeding schedules", "pages/settings/_herd.html"),
    ("Rabbitry", "reminders", "Reminders", "pages/settings/_herd.html"),
    ("Preferences", "appearance", "Appearance", "pages/settings/_appearance.html"),
    ("Preferences", "tabs", "Bottom bar", "pages/settings/_tabs.html"),
    ("Preferences", "export", "Data and export", "pages/settings/_export.html"),
    ("Account", "account", "Sign-in and passkeys", "pages/settings/_account.html"),
]


def settings_sections(current_theme=""):
    return [{"group": g, "anchor": a, "label": l, "template": t, "note": current_theme if a == "appearance" else ""}
            for g, a, l, t in SETTINGS_SECTIONS]


def settings_nav(sections):
    """Group consecutive sections for the sub-nav: [(group, [(anchor, label, note)])]."""
    groups = []
    for s in sections:
        if not groups or groups[-1][0] != s["group"]:
            groups.append((s["group"], []))
        groups[-1][1].append((s["anchor"], s["label"], s["note"]))
    return groups


@login_required
def account(request):
    """Settings: appearance (theme, grid density), account, export, log out.
    The appearance form posts back here and works without JS."""
    user = request.user
    if request.method == "POST":
        theme = request.POST.get("ui_theme", user.ui_theme)
        density = request.POST.get("ui_density", user.ui_density)
        mode = request.POST.get("ui_mode", user.ui_mode)
        if theme in dict(user.THEMES) and density in dict(user.DENSITIES) and mode in dict(user.MODES):
            user.ui_theme, user.ui_density, user.ui_mode = theme, density, mode
            user.save(update_fields=["ui_theme", "ui_density", "ui_mode"])
            if request.headers.get("X-Requested-With") == "fetch":
                return HttpResponse(status=204)
            messages.success(request, "Settings saved.")
        return redirect(request.POST.get("next") if url_has_allowed_host_and_scheme(request.POST.get("next", ""), {request.get_host()}) else "account")
    kinds = [("rabbits", "Rabbits"), ("litters", "Litters"), ("weights", "Weights"), ("shows", "Show results"), ("costs", "Costs")]
    themes = [
        {"key": key, "label": label, "swatch": THEME_SWATCHES[key], "dark": theme_dark_swatch(key),
         "current": key == user.ui_theme}
        for key, label in user.THEMES
    ]
    from .nav import DESTINATIONS, MAX_TABS, clean_tabs, tab_choices

    current = clean_tabs(user.tab_bar)
    slots = [{"index": i + 1, "value": current[i] if i < len(current) else "", "required": i < 3} for i in range(MAX_TABS)]
    destinations = [(key, DESTINATIONS[key][0]) for key in tab_choices()]
    current_theme = dict(user.THEMES).get(user.ui_theme, "")
    sections = settings_sections(current_theme)
    return render(request, "pages/account.html", {"export_kinds": kinds, "themes": themes, "settings_sections": sections, "settings_nav": settings_nav(sections), "wide": True,
                                                  "tab_slots": slots, "tab_destinations": destinations})


@login_required
def tabs(request):
    """Save the phone bottom bar: 3 to 5 destinations in order. Posted by the
    edit mode on the bar (JSON reply) or the Settings form (redirect)."""
    from .nav import DEFAULT_TABS, MAX_TABS, MIN_TABS, tab_choices

    if request.method == "POST":
        if request.POST.get("reset"):
            keys = list(DEFAULT_TABS)
        else:
            keys = [k for k in request.POST.getlist("tab") if k]
        valid = (MIN_TABS <= len(keys) <= MAX_TABS and len(set(keys)) == len(keys)
                 and all(k in tab_choices() for k in keys))
        cleaned = keys if valid else []
        if valid:
            request.user.tab_bar = cleaned
            request.user.save(update_fields=["tab_bar"])
        if request.headers.get("X-Requested-With") == "fetch":
            return JsonResponse({"ok": bool(valid), "tabs": cleaned}, status=200 if valid else 400)
        if valid:
            messages.success(request, "Bottom bar saved.")
        else:
            messages.error(request, "Pick 3 to 5 different tabs.")
    return redirect(reverse("account") + "#tabs")


def menu(request):
    """The old Menu page. Its sections are in the side menu and drawer now; old links go to Settings."""
    return redirect("account")


def components(request):
    """Show every partial. Staff only, or anyone while DEBUG is on."""
    if not settings.DEBUG and not request.user.is_staff:
        raise Http404()
    invalid = ComponentExampleForm(
        data={
            "name": "",
            "email": "not-an-email",
            "password": "",
            "notes": "",
            "status": "",
            "born": "yesterday",
        }
    )
    invalid.is_valid()
    return render(
        request,
        "pages/components.html",
        {
            "example_form": ComponentExampleForm(),
            "invalid_form": invalid,
            "list_items": ["Clover", "Thistle"],
            "empty_items": [],
            "table_columns": ["Name", "Sex"],
            "table_rows": [["Clover", "Doe"]],
            "empty_rows": [],
        },
    )


def day_label(when, today):
    if when == today:
        return "Today"
    if when == today - datetime.timedelta(days=1):
        return "Yesterday"
    return f"{when:%b} {when.day}" + (f", {when.year}" if when.year != today.year else "")


def home_context(user, limit=8):
    """Only real data: herd counts by status and the latest things that
    happened (rabbits added, photos added, deaths, archiving)."""
    from rabbits.models import Rabbit, RabbitPhoto
    from rabbits.tasks import open_items

    today = timezone.localdate()
    rabbits = list(Rabbit.objects.filter(owner=user))
    live = [r for r in rabbits if r.archived_at is None]
    # The same "active" as the Rabbits list: living rabbits still in the herd.
    active = [r for r in live if r.status not in Rabbit.FORMER]
    statuses = [
        {"label": label, "count": sum(1 for r in active if r.status == value), "value": value}
        for value, label in Rabbit.Status.choices if value not in Rabbit.FORMER
    ]
    events = []
    for r in rabbits:
        events.append((timezone.localtime(r.created_at).date(), 3, f"Added {r.name} to the herd", "", r))
        if r.status == Rabbit.Status.DECEASED and r.death_date:
            events.append((r.death_date, 2, f"{r.name} died", r.death_cause, r))
        if r.archived_at:
            events.append((timezone.localtime(r.archived_at).date(), 1, f"Archived {r.name}", "", r))
    for photo in RabbitPhoto.objects.filter(rabbit__owner=user).select_related("rabbit").order_by("-uploaded_at")[:limit]:
        events.append((timezone.localtime(photo.uploaded_at).date(), 0, f"Added a photo of {photo.rabbit.name}", "", photo.rabbit))
    events.sort(key=lambda e: (e[0], e[1]), reverse=True)
    recent = [
        {"title": title, "when": day_label(when, today), "note": note, "rabbit": rabbit}
        for when, _, title, note, rabbit in events[:limit]
    ]
    items = open_items(user, today)
    week_end = today + datetime.timedelta(days=7)
    context = {
        "wide": True,
        "today": today,
        "due_now": [i for i in items if i["date"] <= today],
        "this_week": [i for i in items if today < i["date"] <= week_end],
        "litters": active_litters(user, today),
        "watch": watch_list(user, today),
        "herd": {
            "active": len(active),
            "does": sum(1 for r in active if r.sex == Rabbit.Sex.DOE),
            "bucks": sum(1 for r in active if r.sex == Rabbit.Sex.BUCK),
            "statuses": [s for s in statuses if s["count"]],
            "deceased": sum(1 for r in live if r.status == Rabbit.Status.DECEASED),
            "archived": len(rabbits) - len(live),
        },
        "recent": recent,
        "next_up": items[:5],
        **herd_first(user, today, active, rabbits, items),
    }
    context["progress_count"] = len(context["pairings_progress"]) + len(context["litters"])
    context["week_count"] = len(context["week_now"]) + len(context["week_later"])
    return context


HERD_CARDS = 8
FORMER_CHIPS = 6


def herd_first(user, today, active, rabbits, items):
    """Today, herd first: rabbit cards with their next date, the former herd,
    stat tiles, pairings in progress and recent weights. Real data only."""
    from rabbits.models import Litter, Rabbit, Weight

    week_end = today + datetime.timedelta(days=7)
    photos = {r.pk: r for r in Rabbit.objects.filter(owner=user).prefetch_related("photos")}
    next_for = {}
    for item in items:
        rabbit = item.get("rabbit")
        if rabbit and rabbit.pk not in next_for:
            next_for[rabbit.pk] = item
    latest_weight = {}
    for w in Weight.objects.filter(rabbit__owner=user).order_by("rabbit_id", "-date", "-pk"):
        latest_weight.setdefault(w.rabbit_id, w)
    living = [r for r in active if r.status in (Rabbit.Status.BREEDING, Rabbit.Status.GROWING)]
    living.sort(key=lambda r: (next_for[r.pk]["date"] if r.pk in next_for else datetime.date.max, r.name))
    open_litters = list(Litter.objects.filter(owner=user, kindled_on__isnull=True).select_related("pairing__doe", "pairing__buck")
                        .prefetch_related("pairing__doe__photos", "pairing__buck__photos").order_by("bred_on"))
    bred_status = {lit.pairing.doe_id for lit in open_litters}
    cards = []
    for r in living[:HERD_CARDS]:
        item = next_for.get(r.pk)
        weight = latest_weight.get(r.pk)
        if item:
            when = "today" if item["date"] == today else f"{item['date']:%a, %b} {item['date'].day}"
            label = item["title"].split(":")[0] if item["kind"] == "litter" else item["title"]
            nxt = f"{label} {when}" if item["date"] >= today else f"{label}, overdue"
        elif weight:
            nxt = f"Weighed {weight.date:%a, %b} {weight.date.day}"
        else:
            nxt = ""
        chip = "Bred" if r.pk in bred_status else r.get_status_display()
        cards.append({"rabbit": photos.get(r.pk, r), "chip": chip, "next": nxt, "overdue": bool(item and item["date"] < today)})
    former = [r for r in rabbits if r.archived_at is None and r.status in (Rabbit.Status.SOLD, Rabbit.Status.CULLED, Rabbit.Status.DECEASED)]
    former.sort(key=lambda r: (r.death_date or datetime.date.min, r.pk), reverse=True)
    former_chips = [{"rabbit": photos.get(r.pk, r), "note": r.get_status_display() + (f" {r.death_date:%a, %b} {r.death_date.day}" if r.death_date else "")}
                    for r in former[:FORMER_CHIPS]]
    pairings = []
    for lit in open_litters:
        s = lit.schedule
        palpate, due = lit.day(s.palpate_day), lit.due_on
        stage = 2 if lit.palpated else (1 if today >= lit.bred_on else 0)
        pairings.append({"litter": lit, "doe": photos.get(lit.pairing.doe_id, lit.pairing.doe), "buck": photos.get(lit.pairing.buck_id, lit.pairing.buck),
                         "steps": [{"label": "Bred", "date": lit.bred_on, "state": "done"},
                                   {"label": "Palpated" if lit.palpated else "Palpate", "date": palpate, "state": "done" if lit.palpated else ("next" if stage == 1 else "")},
                                   {"label": "Due", "date": due, "state": "next" if lit.palpated else ""}],
                         "due": due})
    next_kindling = min(pairings, key=lambda p: p["due"]) if pairings else None
    weights = []
    seen = set()
    recent = Weight.objects.filter(rabbit__owner=user, rabbit__archived_at__isnull=True).select_related("rabbit").order_by("-date", "-pk")
    for w in recent.iterator():
        # One row per rabbit: its latest weight.
        if w.rabbit_id in seen:
            continue
        seen.add(w.rabbit_id)
        if len(seen) > 4:
            break
        before = Weight.objects.filter(rabbit=w.rabbit, date__lt=w.date).order_by("-date", "-pk").first()
        delta = w.grams - before.grams if before else None
        weights.append({"weight": w, "rabbit": photos.get(w.rabbit_id, w.rabbit), "delta": delta_text(delta, w.unit) if delta else ""})
    week = [i for i in items if i["date"] <= week_end]
    return {
        "herd_cards": cards,
        "herd_more": max(len(living) - HERD_CARDS, 0),
        "former_chips": former_chips,
        "tiles": {
            "herd": len(living), "bucks": sum(1 for r in living if r.sex == Rabbit.Sex.BUCK),
            "does": sum(1 for r in living if r.sex == Rabbit.Sex.DOE),
            "bred": len(pairings), "bred_names": ", ".join(p["litter"].pairing.doe.name for p in pairings[:3]),
            "next_kindling": next_kindling, "next_days": (next_kindling["due"] - today).days if next_kindling else None,
            "sold": sum(1 for r in former if r.status == Rabbit.Status.SOLD),
            "culled": sum(1 for r in former if r.status == Rabbit.Status.CULLED),
            "deceased": sum(1 for r in former if r.status == Rabbit.Status.DECEASED),
        },
        "pairings_progress": pairings,
        "week_now": [i for i in week if i["date"] <= today],
        "week_later": [i for i in week if i["date"] > today],
        "recent_weights": weights,
    }


def delta_text(grams, unit):
    """A signed weight change, like +4 oz or −120 g."""
    from rabbits.models import weight_text

    sign = "+" if grams > 0 else "−"
    return sign + weight_text(abs(grams), unit)


UNDER_AVERAGE = 0.85  # a kit under 85% of its litter's average is watched


def kit_weights(litter):
    """Each surviving kit with its latest weight, and the litter average."""
    kits = []
    for kit in litter.kits.all():
        if kit.archived_at or kit.status == "deceased":
            continue
        weights = list(kit.weights.all())
        kits.append({"rabbit": kit, "weight": weights[-1] if weights else None})
    weighed = [k["weight"].grams for k in kits if k["weight"]]
    average = round(sum(weighed) / len(weighed)) if weighed else None
    for kit in kits:
        kit["behind"] = bool(average and kit["weight"] and kit["weight"].grams < average * UNDER_AVERAGE)
    return kits, average


def active_litters(user, today):
    """Kindled litters not yet processed, youngest first, with kit age and weights."""
    from rabbits.models import Litter, weight_text

    rows = []
    litters = (Litter.objects.filter(owner=user, kindled_on__isnull=False, processed=False)
               .select_related("pairing__doe", "pairing__buck").prefetch_related("kits__weights"))
    for litter in litters:
        age = (today - litter.kindled_on).days
        if age > Litter.PROCESS_AGE + 30:
            continue
        kits, average = kit_weights(litter)
        rows.append({"litter": litter, "age": age, "kits": len(kits) or litter.survivors or 0,
                     "behind": sum(1 for k in kits if k["behind"]), "average": average,
                     "average_text": weight_text(average, next(k["weight"].unit for k in kits if k["weight"])) if average else ""})
    rows.sort(key=lambda row: row["age"])
    return rows


def watch_list(user, today):
    """Health follow-ups that are still open, and kits well under their litter's average."""
    from rabbits.models import HealthNote

    items = []
    notes = (HealthNote.objects.filter(rabbit__owner=user, follow_up_on__isnull=False, task__done_at__isnull=True,
                                       follow_up_on__lte=today + datetime.timedelta(days=7))
             .select_related("rabbit", "task").order_by("follow_up_on"))
    for note in notes:
        days = (note.follow_up_on - today).days
        when = "recheck today" if days == 0 else (f"recheck overdue {-days} day{'s' if days != -1 else ''}" if days < 0
                                                  else f"recheck {note.follow_up_on:%a}")
        items.append({"title": f"{note.rabbit.name} · {note.get_kind_display().lower()}",
                      "detail": f"Noted {note.date:%b} {note.date.day} · {when}", "urgent": days <= 0,
                      "url": f"/rabbits/{note.rabbit_id}/#health", "task": note.task})
    for row in active_litters(user, today):
        kits, average = kit_weights(row["litter"])
        for kit in kits:
            if kit["behind"]:
                under = round(100 - kit["weight"].grams * 100 / average)
                items.append({"title": kit["rabbit"].name, "detail": f"{kit['weight'].text} · {under}% under litter average",
                              "urgent": True, "url": f"/rabbits/{kit['rabbit'].pk}/#weights", "task": None})
    return items
