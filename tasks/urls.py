from django.urls import path

from . import admin_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tableros/<int:pk>/", views.board_detail, name="board_detail"),
    path("tareas/nueva/", views.task_create, name="task_create"),
    path("tareas/<int:pk>/", views.task_detail, name="task_detail"),
    path("tareas/<int:pk>/editar/", views.task_edit, name="task_edit"),
    path("tareas/<int:pk>/eliminar/", views.task_delete, name="task_delete"),
    path("tareas/<int:pk>/mover/", views.task_move, name="task_move"),
    path("tareas/<int:pk>/completar/", views.task_complete, name="task_complete"),
    path("tableros/nuevo/", views.board_create, name="board_create"),
    path("tareas/<int:task_pk>/actividades/nueva/", views.activity_create, name="activity_create"),
    path("actividades/<int:pk>/alternar/", views.activity_toggle, name="activity_toggle"),
    path("actividades/<int:pk>/mover/", views.activity_move, name="activity_move"),
    path("actividades/<int:pk>/eliminar/", views.activity_delete, name="activity_delete"),
    path("preferencias/notificaciones/", views.notification_preferences, name="notification_preferences"),
    path("panel-admin/", admin_views.control_panel, name="control_panel"),
    path("panel-admin/usuarios/nuevo/", admin_views.create_user, name="managed_user_create"),
    path("panel-admin/usuarios/<int:pk>/alertas/", admin_views.user_alerts, name="managed_user_alerts"),
    path("panel-admin/notificaciones/guardar/", admin_views.save_notifications, name="save_notification_config"),
]
