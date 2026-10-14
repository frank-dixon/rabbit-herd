"""The one date format: "Tue, Oct 13", with the year added only when it isn't this year. {{ day|day }} (a builtin)."""
import datetime

from django import template
from django.utils import timezone

register = template.Library()


def short_date(day, today=None):
    if not day:
        return ""
    if isinstance(day, datetime.datetime):
        day = timezone.localtime(day).date() if timezone.is_aware(day) else day.date()
    today = today or timezone.localdate()
    text = f"{day:%a, %b} {day.day}"
    return text if day.year == today.year else f"{text}, {day.year}"


register.filter("day", short_date)
