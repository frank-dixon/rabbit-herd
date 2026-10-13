from django.urls import path

from . import tasks

urlpatterns = [
    path("", tasks.task_list, name="task_list"),
    path("<int:pk>/done/", tasks.task_done, name="task_done"),
    path("<int:pk>/edit/", tasks.task_edit, name="task_edit"),
    path("<int:pk>/delete/", tasks.task_delete, name="task_delete"),
]
