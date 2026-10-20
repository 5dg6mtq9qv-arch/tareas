from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from tasks.models import NotificationLog, NotificationSettings, Task
from tasks.services import get_notification_config, send_task_email, send_task_telegram


class Command(BaseCommand):
    help = "Envía una vez los recordatorios de las tareas próximas a vencer."

    def handle(self, *args, **options):
        now = timezone.now()
        config = get_notification_config()
        sent = 0
        for user in get_user_model().objects.filter(is_active=True, notification_settings__isnull=True):
            NotificationSettings.objects.get_or_create(user=user)
        preferences = NotificationSettings.objects.select_related("user").filter(
            Q(email_enabled=True) | Q(telegram_enabled=True)
        )
        for pref in preferences:
            limit = now + timedelta(minutes=pref.reminder_minutes)
            tasks = Task.objects.select_related("board").filter(owner=pref.user, completed_at__isnull=True, due_at__gte=now, due_at__lte=limit)
            for task in tasks:
                key = task.due_at.isoformat()
                channels = []
                if pref.email_enabled:
                    channels.append((NotificationLog.Channel.EMAIL, lambda: send_task_email(pref.user, task, config)))
                if pref.telegram_enabled:
                    channels.append((NotificationLog.Channel.TELEGRAM, lambda: send_task_telegram(pref.telegram_chat_id, task, config)))
                for channel, sender in channels:
                    if NotificationLog.objects.filter(task=task, channel=channel, reminder_key=key).exists():
                        continue
                    try:
                        if sender():
                            NotificationLog.objects.create(task=task, channel=channel, reminder_key=key)
                            sent += 1
                    except Exception as exc:
                        self.stderr.write(f"No se pudo avisar sobre tarea {task.pk} por {channel}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Avisos enviados: {sent}"))
