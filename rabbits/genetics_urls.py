from django.urls import path

from . import cross

urlpatterns = [
    path("cross/", cross.cross_view, name="genetics_cross"),
]
