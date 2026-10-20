from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import Activity, Board, NotificationConfiguration, NotificationSettings, Task


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["board", "title", "description", "start_at", "due_at", "priority"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["board"].queryset = Board.objects.filter(owner=user)
        self.fields["board"].label = "Lista"


class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ["name", "description", "color"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "color": forms.TextInput(attrs={"type": "color"})}


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["title"]
        widgets = {"title": forms.TextInput(attrs={"placeholder": "Agregar una subtarea…", "autocomplete": "off"})}


class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = NotificationSettings
        fields = ["email_enabled", "telegram_enabled", "telegram_chat_id", "reminder_minutes"]


class ManagedUserCreationForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico", required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name")


class NotificationConfigurationForm(forms.ModelForm):
    BACKENDS = [
        ("django.core.mail.backends.console.EmailBackend", "Consola (pruebas locales)"),
        ("django.core.mail.backends.smtp.EmailBackend", "SMTP"),
    ]
    email_backend = forms.ChoiceField(label="Tipo de correo", choices=BACKENDS)
    email_password = forms.CharField(
        label="Contraseña SMTP", required=False, widget=forms.PasswordInput,
        help_text="Déjala vacía para conservar la contraseña guardada.",
    )
    telegram_bot_token = forms.CharField(
        label="Token del bot de Telegram", required=False, widget=forms.PasswordInput,
        help_text="Déjalo vacío para conservar el token guardado.",
    )

    class Meta:
        model = NotificationConfiguration
        fields = [
            "email_backend", "email_host", "email_port", "email_username",
            "email_password", "email_use_tls", "default_from_email", "telegram_bot_token",
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("email_backend") == "django.core.mail.backends.smtp.EmailBackend":
            if not cleaned.get("email_host"):
                self.add_error("email_host", "Indica el servidor SMTP.")
            if not cleaned.get("email_username"):
                self.add_error("email_username", "Indica el usuario SMTP.")
        return cleaned

    def save(self, commit=True):
        config = super().save(commit=False)
        for field in ("email_password", "telegram_bot_token"):
            if not self.cleaned_data.get(field) and self.instance.pk:
                setattr(config, field, self.initial.get(field, ""))
        if commit:
            config.save()
        return config
