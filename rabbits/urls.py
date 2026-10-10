from django.urls import path

from . import views

urlpatterns = [
    path("", views.rabbit_list, name="rabbit_list"),
    path("archived/", views.rabbit_archived, name="rabbit_archived"),
    path("new/", views.rabbit_create, name="rabbit_create"),
    path("<int:pk>/", views.rabbit_detail, name="rabbit_detail"),
    path("<int:pk>/edit/", views.rabbit_edit, name="rabbit_edit"),
    path("<int:pk>/archive/", views.rabbit_archive, name="rabbit_archive"),
    path("<int:pk>/restore/", views.rabbit_restore, name="rabbit_restore"),
]
