from django import template

from rabbits.status_pills import tone

register = template.Library()


@register.filter
def status_tone(label):
    """{{ label|status_tone }}: r, y, b, g or "" from the one status map (rabbits/status_pills.py)."""
    return tone(label)


@register.inclusion_tag("components/status_pill.html")
def status_pill(label, extra=""):
    """{% status_pill label %}: a pill whose color and icon come from the status map."""
    return {"label": label, "tone": tone(label), "extra": extra}
