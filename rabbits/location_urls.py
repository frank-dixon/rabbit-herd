from django.urls import path

from . import location_views

urlpatterns = [
    path("", location_views.location_list, name="location_list"),
    path("<int:pk>/", location_views.location_edit, name="location_edit"),
]
