from django import template

from ..models import prefs
from ..settings_forms import SECTIONS

register = template.Library()


@register.inclusion_tag("rabbits/_herd_settings.html", takes_context=True)
def herd_settings_sections(context):
    instance = prefs(context["request"].user)
    return {"forms": {name: form_class(instance=instance) for name, form_class in SECTIONS.items()},
            "csrf_token": context.get("csrf_token")}
