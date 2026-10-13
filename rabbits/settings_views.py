"""Herd sections of the Settings page: units, breeding schedule, rabbitry
and reminders. Each section is its own form that posts here and returns to
/settings/; works without JavaScript."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import HerdSettings
from .settings_forms import SECTIONS

TITLES = {"units": "Units", "schedule": "Breeding schedule", "rabbitry": "Rabbitry", "reminders": "Reminders"}


@login_required
@require_POST
def settings_save(request, section):
    form_class = SECTIONS.get(section)
    if form_class is None:
        raise Http404()
    instance = HerdSettings.objects.filter(user=request.user).first() or HerdSettings(user=request.user)
    form = form_class(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, f"{TITLES[section]} saved.")
        return redirect(reverse("account") + f"#{section}")
    items = [{"anchor": f"id_{name}", "message": error} for name, errors in form.errors.items() for error in errors]
    return render(request, "rabbits/settings_section.html",
                  {"section": section, "title": TITLES[section], "form": form, "items": items}, status=400)
