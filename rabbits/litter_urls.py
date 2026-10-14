from django.urls import path

from . import weigh_in

from . import kit_compare, litter_check_views, litter_photos, litters, siblings

urlpatterns = [
    path("", litters.litter_list, name="litter_list"),
    path("<int:pk>/", litters.litter_detail, name="litter_detail"),
    path("<int:pk>/weigh/", weigh_in.weigh_in, name="litter_weigh_in"),
    path("<int:pk>/compare/", kit_compare.litter_compare, name="litter_compare"),
    path("<int:pk>/siblings/", siblings.litter_siblings, name="litter_siblings"),
    path("<int:pk>/covers/", litters.cover_add, name="cover_add"),
    path("<int:pk>/covers/<int:cover_pk>/delete/", litters.cover_delete, name="cover_delete"),
    path("<int:pk>/task/", litters.litter_task, name="litter_task"),
    path("<int:pk>/kindling/", litters.litter_kindle, name="litter_kindle"),
    path("<int:pk>/kits/", litters.litter_add_kit, name="litter_add_kit"),
    path("<int:pk>/checks/", litter_check_views.litter_check, name="litter_check"),
    path("<int:pk>/convert/", litter_check_views.litter_convert, name="litter_convert"),
    path("<int:pk>/photo/", litter_photos.litter_photo, name="litter_photo"),
    path("<int:pk>/kits/<int:number>/photo/", litter_photos.kit_photo, name="kit_photo"),
    path("<int:pk>/notes/", litters.litter_note_add, name="litter_note_add"),
    path("<int:pk>/delete/", litters.litter_delete, name="litter_delete"),
]
