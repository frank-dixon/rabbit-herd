"""Daily summary emails: what's due today and overdue, for the kinds of
dates each keeper chose in Settings. send_due() is run by the
send_daily_summaries command, which a scheduler calls every few minutes;
each keeper gets at most one email a day, at or after their chosen time."""

import datetime

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.emails import send_account_mail

from .models import HerdSettings
from .tasks import open_items


def wanted(item, prefs):
    key = "task" if item["kind"] == "task" else item.get("key", "")
    field = HerdSettings.REMINDER_KEYS.get(key)
    return bool(field and getattr(prefs, field))


def summary(user, prefs, today):
    """(subject, body) for one keeper, or None when nothing is due."""
    items = [item for item in open_items(user, today, samples=False) if item["date"] <= today and wanted(item, prefs)]
    if not items:
        return None
    overdue = [item for item in items if item["date"] < today]
    due = [item for item in items if item["date"] == today]
    lines = []
    if due:
        lines += ["Due today:"] + [f"- {item['title']}" for item in due] + [""]
    if overdue:
        lines += ["Overdue:"] + [f"- {item['title']} (since {item['date']:%b} {item['date'].day})" for item in overdue] + [""]
    host = getattr(settings, "APP_HOSTNAME", "") or ""
    tasks_url = f"https://{host}{reverse('task_list')}" if host else reverse("task_list")
    lines += [f"All tasks: {tasks_url}", "", "Change these emails in Settings, under Reminders."]
    count = len(items)
    subject = f"{settings.APP_NAME}: {count} thing{'s' if count != 1 else ''} due {today:%a, %b} {today.day}"
    return subject, "\n".join(lines)


def send_due(now=None):
    """Send each keeper's summary once their time has come today. Returns
    how many were sent."""
    now = timezone.localtime(now)
    today, sent = now.date(), 0
    rows = HerdSettings.objects.filter(daily_email=True, daily_email_time__lte=now.time()).exclude(
        daily_email_sent_on=today).select_related("user")
    for prefs in rows:
        user = prefs.user
        if not user.is_active or user.is_guest or not user.email:
            continue
        user._herd_settings_cache = prefs
        message = summary(user, prefs, today)
        if message:
            send_account_mail(*message, user.email)
            sent += 1
        prefs.daily_email_sent_on = today
        prefs.save(update_fields=["daily_email_sent_on"])
    return sent
