from django.urls import path

from . import costs

urlpatterns = [
    path("", costs.cost_list, name="cost_list"),
    path("<int:pk>/", costs.cost_edit, name="cost_edit"),
    path("<int:pk>/delete/", costs.cost_delete, name="cost_delete"),
]
