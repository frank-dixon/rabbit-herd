from django.urls import path

from . import litters, pairings, schedules

urlpatterns = [
    path("", pairings.pairing_list, name="pairing_list"),
    path("<int:pk>/", pairings.pairing_detail, name="pairing_detail"),
    path("<int:pk>/delete/", pairings.pairing_delete, name="pairing_delete"),
    path("<int:pk>/litters/", litters.litter_create, name="litter_create"),
    path("<int:pk>/schedule/", schedules.pairing_schedule, name="pairing_schedule"),
]
