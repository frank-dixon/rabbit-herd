from django.urls import path

from . import costs

urlpatterns = [
    path("", costs.cost_list, name="cost_list"),
    path("new/", costs.cost_new, name="cost_new"),
    path("<int:pk>/", costs.cost_edit, name="cost_edit"),
    path("<int:pk>/edit/", costs.cost_edit, name="cost_edit_form"),
    path("<int:pk>/delete/", costs.cost_delete, name="cost_delete"),
]
