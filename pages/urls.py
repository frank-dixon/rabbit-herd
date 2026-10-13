from django.urls import path

from . import pwa, views

urlpatterns = [
    path("components/", views.components, name="components"),
    path("account/", views.account, name="account"),
    path("manifest.webmanifest", pwa.manifest, name="pwa_manifest"),
    path("sw.js", pwa.service_worker, name="pwa_service_worker"),
    path("offline/", pwa.offline, name="pwa_offline"),
    path("", views.index, name="index"),
]
