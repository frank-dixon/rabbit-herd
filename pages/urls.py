from django.urls import path

from . import views

urlpatterns = [
    path("components/", views.components, name="components"),
    path("", views.index, name="index"),
]
