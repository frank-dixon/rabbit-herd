from django.urls import path

from . import hub_views, weights_page

urlpatterns = [
    path("weights/", weights_page.weights_hub, name="weights_hub"),
    path("weights/group/", weights_page.weigh_group, name="weigh_group"),
    path("weights/<int:pk>/log/", weights_page.weight_log, name="weights_log"),
    path("health/", hub_views.health_list, name="health_list"),
    path("health/<int:pk>/resolve/", hub_views.health_resolve, name="health_resolve"),
    path("shows/", hub_views.show_list, name="show_list"),
]
