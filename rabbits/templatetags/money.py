from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def money(value):
    """$1,234.50. Empty for None."""
    if value is None or value == "":
        return ""
    return f"${Decimal(value):,.2f}"
