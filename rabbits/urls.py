from django.urls import path

from . import contact_views, location_views, weights, adopt_views, edit_views, flow_views, photo_views, views

urlpatterns = [
    path("", views.rabbit_list, name="rabbit_list"),
    path("<int:pk>/weights/", weights.weight_add, name="rabbit_weight_add"),
    path("weights/<int:pk>/delete/", weights.weight_delete, name="rabbit_weight_delete"),
    path("<int:pk>/location/", location_views.rabbit_location, name="rabbit_location"),
    path("<int:pk>/source/", contact_views.rabbit_source, name="rabbit_source"),
    path("archived/", views.rabbit_archived, name="rabbit_archived"),
    path("new/", flow_views.rabbit_flow_resume, name="rabbit_create"),
    path("new/restart/", flow_views.rabbit_flow_restart, name="rabbit_flow_restart"),
    path("new/added/<int:pk>/", flow_views.rabbit_flow_done, name="rabbit_flow_done"),
    path("new/<slug:step>/", flow_views.rabbit_flow_step, name="rabbit_flow_step"),
    path("photos/<int:pk>/", photo_views.photo_file, name="rabbit_photo_file"),
    path("photos/<int:pk>/notes/", photo_views.photo_notes, name="rabbit_photo_notes"),
    path("photos/<int:pk>/delete/", photo_views.photo_delete, name="rabbit_photo_delete"),
    path("photos/<int:pk>/date/", photo_views.photo_date, name="rabbit_photo_date"),
    path("photos/<int:pk>/rotate/", photo_views.photo_rotate, name="rabbit_photo_rotate"),
    path("photos/<int:pk>/main/", photo_views.photo_set_main, name="rabbit_photo_set_main"),
    path("<int:pk>/photos/", photo_views.rabbit_photos, name="rabbit_photos"),
    path("<int:pk>/", views.rabbit_detail, name="rabbit_detail"),
    path("<int:pk>/edit/", edit_views.rabbit_edit, name="rabbit_edit"),
    path("<int:pk>/edit/<slug:step>/", edit_views.rabbit_edit_step, name="rabbit_edit_step"),
    path("<int:pk>/genes/", views.rabbit_genes, name="rabbit_genes"),
    path("<int:pk>/c-carrier/", views.rabbit_c_carrier, name="rabbit_c_carrier"),
    path("<int:pk>/archive/", views.rabbit_archive, name="rabbit_archive"),
    path("relatives/<int:pk>/add-to-herd/", adopt_views.relative_add_to_herd, name="relative_add_to_herd"),
    path("<int:pk>/delete/", views.rabbit_delete, name="rabbit_delete"),
    path("<int:pk>/restore/", views.rabbit_restore, name="rabbit_restore"),
]
