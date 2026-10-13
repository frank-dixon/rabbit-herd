from django.urls import path

from . import waitlist

urlpatterns = [
    path("", waitlist.waitlist, name="waitlist"),
    path("<int:pk>/", waitlist.waitlist_edit, name="waitlist_edit"),
    path("<int:pk>/delete/", waitlist.waitlist_delete, name="waitlist_delete"),
]
