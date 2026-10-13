from django import template

from ..models import prefs
from ..settings_forms import SECTIONS

register = template.Library()


@register.filter
def weigh(grams, user):
    """Grams as text in the user's chosen unit: {{ weight.grams|weigh:request.user }}."""
    from ..models import weight_text

    return weight_text(grams, prefs(user).weight_unit) if grams else ""


@register.inclusion_tag("rabbits/_herd_settings.html", takes_context=True)
def herd_settings_sections(context, only=None):
    instance = prefs(context["request"].user)
    names = [only] if only else list(SECTIONS)
    return {"forms": {name: SECTIONS[name](instance=instance) for name in names},
            "csrf_token": context.get("csrf_token"),
            "schedules": list(context["request"].user.breeding_schedules.all())}
