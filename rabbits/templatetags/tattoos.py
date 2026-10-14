from django import template

register = template.Library()


@register.simple_tag
def next_tattoo(user):
    """The tattoo the next new rabbit would be offered, for the Settings preview."""
    from rabbits.tattoo import suggest

    return suggest(user) if user and user.pk else ""
