from django.urls import path

from . import views

urlpatterns = [
    path("components/", views.components, name="components"),
    path("account/", views.account, name="account"),
    path("", views.index, name="index"),
]
