from django.contrib import admin
from django.urls import include, path
from accounts.urls import auth_urlpatterns

from rabbits.export import export_csv
from rabbits import glossary, schedules
from rabbits.settings_views import settings_save

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
    path("settings/schedules/new/", schedules.schedule_form, name="schedule_add"),
    path("settings/schedules/<int:pk>/", schedules.schedule_form, name="schedule_edit"),
    path("settings/schedules/<int:pk>/delete/", schedules.schedule_delete, name="schedule_delete"),
    path("settings/herd/<slug:section>/", settings_save, name="herd_settings_save"),
    path("", include("rabbits.hub_urls")),
    path("", include("pages.urls")),
]

handler400 = "pages.errors.bad_request"
handler403 = "pages.errors.permission_denied"
handler404 = "pages.errors.page_not_found"
# handler500 stays Django's default: it renders templates/500.html with no context.
