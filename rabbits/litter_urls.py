from django.urls import path

from . import litters

urlpatterns = [
    path("", litters.litter_list, name="litter_list"),
    path("<int:pk>/", litters.litter_detail, name="litter_detail"),
    path("<int:pk>/task/", litters.litter_task, name="litter_task"),
    path("<int:pk>/kindling/", litters.litter_kindle, name="litter_kindle"),
    path("<int:pk>/kits/", litters.litter_add_kit, name="litter_add_kit"),
    path("<int:pk>/delete/", litters.litter_delete, name="litter_delete"),
]
