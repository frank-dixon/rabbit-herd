from django.urls import path

from . import pairings

urlpatterns = [
    path("", pairings.pairing_list, name="pairing_list"),
    path("<int:pk>/", pairings.pairing_detail, name="pairing_detail"),
    path("<int:pk>/delete/", pairings.pairing_delete, name="pairing_delete"),
]
