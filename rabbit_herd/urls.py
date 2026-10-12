from django.contrib import admin
from django.urls import include, path

# Uploaded photos have no public URL. They are served one at a time, to
# their owner only, by rabbits.photo_views.photo_file.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("rabbits/", include("rabbits.urls")),
    path("locations/", include("rabbits.location_urls")),
    path("pairings/", include("rabbits.pairing_urls")),
    path("litters/", include("rabbits.litter_urls")),
    path("contacts/", include("rabbits.contact_urls")),
    path("", include("pages.urls")),
]
