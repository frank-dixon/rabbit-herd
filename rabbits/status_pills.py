"""One color per status, app-wide (Frank, 2026-10-18). Every pill also shows its word.

    g  green  active or healthy
    b  blue   bred or expecting
    y  amber  due soon or needs attention
    r  red    overdue, a problem, or high COI
    o  grey   sold, processed, culled, archived (no longer in the herd)
    (none)    routine, like a checkup: the plain neutral pill

COI maps low / mid / high to green / amber / red (coi_tone). The colors are the
--{g,b,y,r}-soft / -ink tokens and --pill / --ink-2 in assets/themes.css;
pages/test_status_colors.py checks each pair reads at 4.5:1 in every theme."""

TONES = {
    "g": {"active", "breeding", "growing", "in herd", "healthy", "nursing", "kits on ground", "on track", "weaned",
          "keep", "kept", "done", "not related", "low", "low coi", "ready", "picked", "purebred", "counts"},
    "b": {"bred", "expecting", "pregnant", "planned", "waiting", "next", "covered"},
    "y": {"due soon", "due today", "today", "watch", "behind", "behind curve", "treatment", "weigh-in overdue",
          "needs attention", "offered a rabbit", "hold", "open", "related", "mid", "moderate"},
    "r": {"overdue", "sick", "needs action", "action needed", "illness", "injury", "problem", "high", "high coi",
          "closely related"},
    "o": {"sold", "processed", "culled", "cull", "archived", "deceased", "retired", "dead", "former", "reached"},
}
LOOKUP = {label: tone for tone, labels in TONES.items() for label in labels}

# Rabbit.status values -> tone (the list rows, cards and Today chips).
STATUS = {"breeding": "g", "growing": "g", "active": "g", "bred": "b", "expecting": "b",
          "sold": "o", "culled": "o", "processed": "o", "deceased": "o", "archived": "o", "retired": "o"}

COI_MID = 6.25
COI_HIGH = 25.0


def tone(label):
    """The pill tone letter (g, b, y, r, o) for a status word, or "" for neutral."""
    return LOOKUP.get(str(label or "").strip().lower(), "")


def status_tone(status):
    """Tone for a Rabbit.status value."""
    return STATUS.get(str(status or "").strip().lower(), "")


def coi_tone(coi):
    """Low, mid and high inbreeding: green, amber, red."""
    coi = float(coi or 0)
    return "r" if coi >= COI_HIGH else "y" if coi >= COI_MID else "g"
