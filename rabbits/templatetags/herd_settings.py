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
def herd_settings_sections(context):
    instance = prefs(context["request"].user)
    return {"forms": {name: form_class(instance=instance) for name, form_class in SECTIONS.items()},
            "csrf_token": context.get("csrf_token")}
