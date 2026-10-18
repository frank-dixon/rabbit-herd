from django.contrib import admin
from django.urls import include, path
from accounts.urls import auth_urlpatterns

from rabbits.export import export_csv
from rabbits import glossary, schedules
from rabbits.settings_views import settings_save
from rabbits import sample_views
from pages import cron

# Uploaded photos have no public URL. They are served one at a time, to
# their owner only, by rabbits.photo_views.photo_file.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include(auth_urlpatterns)),
    path("rabbits/", include("rabbits.urls")),
    path("locations/", include("rabbits.location_urls")),
    path("pairings/", include("rabbits.pairing_urls")),
    path("litters/", include("rabbits.litter_urls")),
    path("tasks/", include("rabbits.task_urls")),
    path("programs/", include("rabbits.program_urls")),
    path("export/<slug:kind>.csv", export_csv, name="export_csv"),
    path("waitlist/", include("rabbits.waitlist_urls")),
    path("costs/", include("rabbits.cost_urls")),
    path("contacts/", include("rabbits.contact_urls")),
    path("genetics/", include("rabbits.genetics_urls")),
    path("glossary/", glossary.glossary, name="glossary"),
    path("cron/daily/", cron.daily, name="cron_daily"),
    path("settings/schedules/new/", schedules.schedule_form, name="schedule_add"),
    path("settings/schedules/<int:pk>/", schedules.schedule_form, name="schedule_edit"),
    path("settings/schedules/<int:pk>/delete/", schedules.schedule_delete, name="schedule_delete"),
    path("settings/herd/<slug:section>/", settings_save, name="herd_settings_save"),
    path("samples/add/<slug:screen>/", sample_views.samples_add, name="samples_add"),
    path("samples/toggle/", sample_views.samples_toggle, name="samples_toggle"),
    path("samples/clear/", sample_views.samples_clear, name="samples_clear"),
    path("guide/restart/", sample_views.guide_restart, name="guide_restart"),
    path("guide/continue/", sample_views.guide_continue, name="guide_continue"),
    path("guide/skip/", sample_views.guide_skip, name="guide_skip"),
    path("guide/step/", sample_views.guide_step, name="guide_step"),
    path("", include("rabbits.hub_urls")),
    path("", include("pages.urls")),
]

handler400 = "pages.errors.bad_request"
handler403 = "pages.errors.permission_denied"
handler404 = "pages.errors.page_not_found"
# handler500 stays Django's default: it renders templates/500.html with no context.
