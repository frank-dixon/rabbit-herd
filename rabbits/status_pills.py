"""One color per status, app-wide. Red: overdue or action needed. Amber: watch or behind. Blue: expecting.
Green: nursing, healthy, on track. Neutral: everything else. Urgency belongs in the "Next" line, not the pill."""

TONES = {
    "r": {"overdue", "sick", "needs action", "action needed", "illness", "injury", "cull"},
    "y": {"watch", "behind", "behind curve", "treatment", "weigh-in overdue", "offered a rabbit", "hold"},
    "b": {"expecting", "due today", "bred", "due soon", "planned", "waiting"},
    "g": {"nursing", "healthy", "on track", "weaned", "keep", "sold", "done", "checkup"},
}
LOOKUP = {label: tone for tone, labels in TONES.items() for label in labels}


def tone(label):
    """The pill tone letter (r, y, b, g) for a status label, or "" for neutral."""
    return LOOKUP.get(str(label or "").strip().lower(), "")
