from django.urls import path
from django.views.generic import RedirectView

from . import pwa, views

urlpatterns = [
    path("components/", views.components, name="components"),
    path("settings/", views.account, name="account"),
    path("menu/", views.menu, name="app_menu"),
    path("settings/tabs/", views.tabs, name="tab_bar"),
    path("account/", RedirectView.as_view(pattern_name="account", permanent=False)),
    path("manifest.webmanifest", pwa.manifest, name="pwa_manifest"),
    path("sw.js", pwa.service_worker, name="pwa_service_worker"),
    path("offline/", pwa.offline, name="pwa_offline"),
    path("", views.index, name="index"),
]
