from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ManagedUserCreationForm, NotificationConfigurationForm, NotificationSettingsForm
from .models import NotificationConfiguration, NotificationSettings


admin_required = user_passes_test(lambda user: user.is_authenticated and user.is_superuser)


@admin_required
def control_panel(request):
    config = NotificationConfiguration.objects.first() or NotificationConfiguration()
    return render(request, "tasks/admin_panel.html", {
        "users": get_user_model().objects.order_by("username"),
        "config": config,
        "config_form": NotificationConfigurationForm(instance=config),
    })


@admin_required
@require_http_methods(["GET", "POST"])
def create_user(request):
    form = ManagedUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario creado. Ya puede iniciar sesión.")
        return redirect("control_panel")
    return render(request, "tasks/admin_form.html", {"title": "Crear usuario", "form": form})


@admin_required
@require_http_methods(["POST"])
def save_notifications(request):
    config = NotificationConfiguration.objects.first() or NotificationConfiguration()
    form = NotificationConfigurationForm(request.POST, instance=config)
    if form.is_valid():
        form.save()
        messages.success(request, "Configuración de correo y Telegram guardada.")
        return redirect("control_panel")
    return render(request, "tasks/admin_panel.html", {
        "users": get_user_model().objects.order_by("username"),
        "config": config,
        "config_form": form,
    }, status=400)


@admin_required
@require_http_methods(["GET", "POST"])
def user_alerts(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    preferences, _ = NotificationSettings.objects.get_or_create(user=user)
    form = NotificationSettingsForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Alertas de {user.username} actualizadas.")
        return redirect("control_panel")
    return render(request, "tasks/admin_form.html", {
        "title": f"Alertas de {user.username}", "form": form,
    })
