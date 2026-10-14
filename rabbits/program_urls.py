from django.urls import path

from . import program_views as v

urlpatterns = [
    path("", v.program_list, name="program_list"),
    path("new/", v.program_new, name="program_new"),
    path("<int:pk>/", v.program_detail, name="program_detail"),
    path("<int:pk>/goal/", v.program_goal, name="program_goal"),
    path("<int:pk>/breeders/", v.program_breeders, name="program_breeders"),
    path("<int:pk>/outside/", v.program_outside, name="program_outside"),
    path("<int:pk>/g2/", v.program_g2, name="program_g2"),
    path("<int:pk>/schedule/", v.program_schedule, name="program_schedule"),
    path("<int:pk>/delete/", v.program_delete, name="program_delete"),
]
