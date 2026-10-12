from django.urls import path

from . import contact_views

urlpatterns = [
    path("", contact_views.contact_list, name="contact_list"),
    path("new/", contact_views.contact_create, name="contact_create"),
    path("<int:pk>/", contact_views.contact_detail, name="contact_detail"),
    path("<int:pk>/edit/", contact_views.contact_edit, name="contact_edit"),
]
