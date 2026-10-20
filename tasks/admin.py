from django.contrib import admin

from .models import Activity, Board, Column, NotificationConfiguration, NotificationLog, NotificationSettings, Task


class ColumnInline(admin.TabularInline):
    model = Column
    extra = 1


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    list_filter = ["owner"]
    search_fields = ["name", "owner__username"]
    inlines = [ColumnInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "board", "column", "priority", "start_at", "due_at"]
    list_filter = ["priority", "board", "column"]
    search_fields = ["title", "description", "owner__username"]
    autocomplete_fields = ["owner"]
    inlines = [ActivityInline]


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "email_enabled", "telegram_enabled", "reminder_minutes"]


@admin.register(NotificationConfiguration)
class NotificationConfigurationAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Correo", {"fields": ["email_backend", "email_host", "email_port", "email_username", "email_password", "email_use_tls", "default_from_email"]}),
        ("Telegram", {"fields": ["telegram_bot_token"]}),
    ]

    def has_add_permission(self, request):
        return not NotificationConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["task", "channel", "sent_at"]
    list_filter = ["channel", "sent_at"]
    readonly_fields = ["task", "channel", "reminder_key", "sent_at"]
    actions = None

    def has_add_permission(self, request):
        return False

admin.site.site_header = "Administración de Tareas"
admin.site.site_title = "Tareas"
