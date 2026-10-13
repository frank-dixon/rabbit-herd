from django.urls import path

from . import hub_views

urlpatterns = [
    path("weights/", hub_views.weights_hub, name="weights_hub"),
    path("health/", hub_views.health_list, name="health_list"),
    path("shows/", hub_views.show_list, name="show_list"),
]
