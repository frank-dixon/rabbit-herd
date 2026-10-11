from django.urls import path

from . import flow_views, views

urlpatterns = [
    path("", views.rabbit_list, name="rabbit_list"),
    path("archived/", views.rabbit_archived, name="rabbit_archived"),
    path("new/", flow_views.rabbit_flow_resume, name="rabbit_create"),
    path("new/restart/", flow_views.rabbit_flow_restart, name="rabbit_flow_restart"),
    path("new/added/<int:pk>/", flow_views.rabbit_flow_done, name="rabbit_flow_done"),
    path("new/<slug:step>/", flow_views.rabbit_flow_step, name="rabbit_flow_step"),
    path("<int:pk>/", views.rabbit_detail, name="rabbit_detail"),
    path("<int:pk>/edit/", views.rabbit_edit, name="rabbit_edit"),
    path("<int:pk>/archive/", views.rabbit_archive, name="rabbit_archive"),
    path("<int:pk>/restore/", views.rabbit_restore, name="rabbit_restore"),
]
