import requests
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives

from .models import NotificationConfiguration


def get_notification_config():
    return NotificationConfiguration.objects.first()


def send_task_email(user, task, config):
    if not user.email:
        return False
    backend = config.email_backend if config else "django.core.mail.backends.console.EmailBackend"
    options = {}
    if config and backend == "django.core.mail.backends.smtp.EmailBackend":
        options = {"host": config.email_host, "port": config.email_port, "username": config.email_username,
                   "password": config.email_password, "use_tls": config.email_use_tls}
        connection = EmailBackend(**options)
    else:
        connection = get_connection(backend=backend)
    subject = f"Recordatorio: {task.title}"
    due = task.due_at.strftime("%d/%m/%Y %H:%M") if task.due_at else "sin fecha límite"
    body = f"Tu tarea «{task.title}» vence el {due}.\nTablero: {task.board.name}"
    message = EmailMultiAlternatives(subject, body, config.default_from_email if config else "tareas@localhost", [user.email], connection=connection)
    return bool(message.send())


def send_task_telegram(chat_id, task, config):
    if not config or not config.telegram_bot_token or not chat_id:
        return False
    due = task.due_at.strftime("%d/%m/%Y %H:%M") if task.due_at else "sin fecha límite"
    response = requests.post(
        f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": f"⏰ {task.title}\nVence: {due}\nTablero: {task.board.name}"},
        timeout=15,
    )
    response.raise_for_status()
    return True
