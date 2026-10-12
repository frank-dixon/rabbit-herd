from django.urls import path

from . import flow_views, photo_views, views

urlpatterns = [
    path("", views.rabbit_list, name="rabbit_list"),
    path("archived/", views.rabbit_archived, name="rabbit_archived"),
    path("new/", flow_views.rabbit_flow_resume, name="rabbit_create"),
    path("new/restart/", flow_views.rabbit_flow_restart, name="rabbit_flow_restart"),
    path("new/added/<int:pk>/", flow_views.rabbit_flow_done, name="rabbit_flow_done"),
    path("new/<slug:step>/", flow_views.rabbit_flow_step, name="rabbit_flow_step"),
    path("photos/<int:pk>/", photo_views.photo_file, name="rabbit_photo_file"),
    path("photos/<int:pk>/notes/", photo_views.photo_notes, name="rabbit_photo_notes"),
    path("photos/<int:pk>/delete/", photo_views.photo_delete, name="rabbit_photo_delete"),
    path("photos/<int:pk>/main/", photo_views.photo_set_main, name="rabbit_photo_set_main"),
    path("<int:pk>/photos/", photo_views.rabbit_photos, name="rabbit_photos"),
    path("<int:pk>/", views.rabbit_detail, name="rabbit_detail"),
    path("<int:pk>/edit/", views.rabbit_edit, name="rabbit_edit"),
    path("<int:pk>/c-carrier/", views.rabbit_c_carrier, name="rabbit_c_carrier"),
    path("<int:pk>/archive/", views.rabbit_archive, name="rabbit_archive"),
    path("<int:pk>/restore/", views.rabbit_restore, name="rabbit_restore"),
]
