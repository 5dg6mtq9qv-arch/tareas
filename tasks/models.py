from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Board(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="boards", verbose_name="propietario")
    name = models.CharField("nombre", max_length=120)
    description = models.TextField("descripción", blank=True)
    color = models.CharField("color", max_length=7, default="#4f46e5")
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        verbose_name = "tablero"
        verbose_name_plural = "tableros"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_board_name_per_owner")]

    def __str__(self):
        return self.name


class Column(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns", verbose_name="tablero")
    name = models.CharField("nombre", max_length=80)
    position = models.PositiveIntegerField("posición", default=0)
    color = models.CharField("color", max_length=7, default="#64748b")

    class Meta:
        verbose_name = "columna"
        verbose_name_plural = "columnas"
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["board", "name"], name="unique_column_name_per_board")]

    def __str__(self):
        return f"{self.board} · {self.name}"


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"
        URGENT = "urgent", "Urgente"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks", verbose_name="propietario")
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="tasks", verbose_name="tablero")
    column = models.ForeignKey(Column, on_delete=models.PROTECT, related_name="tasks", verbose_name="columna")
    title = models.CharField("título", max_length=200)
    description = models.TextField("descripción", blank=True)
    start_at = models.DateTimeField("fecha de inicio", null=True, blank=True)
    due_at = models.DateTimeField("fecha límite", null=True, blank=True)
    priority = models.CharField("prioridad", max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    position = models.PositiveIntegerField("posición", default=0)
    completed_at = models.DateTimeField("completada", null=True, blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "tarea"
        verbose_name_plural = "tareas"
        ordering = ["position", "due_at", "id"]
        indexes = [models.Index(fields=["owner", "due_at"]), models.Index(fields=["column", "position"])]

    def __str__(self):
        return self.title

    def clean(self):
        if self.column_id and self.board_id and self.column.board_id != self.board_id:
            raise ValidationError({"column": "La columna debe pertenecer al tablero seleccionado."})
        if self.board_id and self.owner_id and self.board.owner_id != self.owner_id:
            raise ValidationError({"board": "El tablero debe pertenecer al propietario de la tarea."})
        if self.start_at and self.due_at and self.due_at < self.start_at:
            raise ValidationError({"due_at": "La fecha límite debe ser posterior a la fecha de inicio."})

    @property
    def is_overdue(self):
        return bool(self.due_at and not self.completed_at and self.due_at < timezone.now())


class Activity(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activities", verbose_name="tarea")
    column = models.ForeignKey(Column, on_delete=models.PROTECT, related_name="activities", verbose_name="estado")
    title = models.CharField("actividad", max_length=200)
    completed = models.BooleanField("completada", default=False)
    position = models.PositiveIntegerField("posición", default=0)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "subtarea"
        verbose_name_plural = "subtareas"
        ordering = ["position", "id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.column_id is None and self.task_id:
            columns = self.task.board.columns
            self.column = columns.order_by("-position", "-id").first() if self.completed else columns.order_by("position", "id").first()
        if self.column_id and self.column.board_id != self.task.board_id:
            raise ValidationError("El estado de la subtarea debe pertenecer a su lista.")
        super().save(*args, **kwargs)


class NotificationSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_settings", verbose_name="usuario")
    email_enabled = models.BooleanField("avisos por correo", default=True)
    telegram_enabled = models.BooleanField("avisos por Telegram", default=False)
    telegram_chat_id = models.CharField("chat ID de Telegram", max_length=80, blank=True)
    reminder_minutes = models.PositiveIntegerField("avisar con anticipación (minutos)", default=60)

    class Meta:
        verbose_name = "preferencia de notificación"
        verbose_name_plural = "preferencias de notificación"

    def __str__(self):
        return f"Avisos de {self.user}"


class NotificationConfiguration(models.Model):
    email_backend = models.CharField("backend de correo", max_length=180, default="django.core.mail.backends.console.EmailBackend")
    email_host = models.CharField("servidor SMTP", max_length=180, blank=True)
    email_port = models.PositiveIntegerField("puerto SMTP", default=587)
    email_username = models.CharField("usuario SMTP", max_length=180, blank=True)
    email_password = models.CharField("contraseña SMTP", max_length=255, blank=True)
    email_use_tls = models.BooleanField("usar TLS", default=True)
    default_from_email = models.EmailField("remitente", default="tareas@localhost")
    telegram_bot_token = models.CharField("token del bot de Telegram", max_length=255, blank=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "configuración global de notificaciones"
        verbose_name_plural = "configuración global de notificaciones"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Correo y Telegram"


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Correo"
        TELEGRAM = "telegram", "Telegram"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notification_logs", verbose_name="tarea")
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    reminder_key = models.CharField("clave del aviso", max_length=80)
    sent_at = models.DateTimeField("enviado", auto_now_add=True)

    class Meta:
        verbose_name = "aviso enviado"
        verbose_name_plural = "avisos enviados"
        constraints = [models.UniqueConstraint(fields=["task", "channel", "reminder_key"], name="unique_task_reminder_channel")]

    def __str__(self):
        return f"{self.task} · {self.get_channel_display()}"
