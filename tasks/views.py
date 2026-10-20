import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ActivityForm, BoardForm, NotificationSettingsForm, TaskForm
from .models import Activity, Board, Column, NotificationSettings, Task
from .progress import progress_by_board, task_progress


def _ensure_default_board(user):
    board = Board.objects.filter(owner=user).first()
    if board:
        return board
    with transaction.atomic():
        board = Board.objects.create(owner=user, name="Mis tareas", description="Tablero personal")
        Column.objects.bulk_create([
            Column(board=board, name="Pendiente", position=0, color="#64748b"),
            Column(board=board, name="En progreso", position=1, color="#f59e0b"),
            Column(board=board, name="Completado", position=2, color="#10b981"),
        ])
    return board


def _first_column(board):
    return board.columns.order_by("position", "id").first()


def _completed_column(board):
    return board.columns.order_by("-position", "-id").first()


def _progress_column(board):
    return board.columns.order_by("position", "id")[1:2].first() or _first_column(board)


def _sync_task_from_subtasks(task):
    """La tarea sigue el avance de sus subtareas."""
    subtasks = list(task.activities.select_related("column"))
    if not subtasks:
        return
    first = _first_column(task.board)
    last = _completed_column(task.board)
    all_completed = all(subtask.completed for subtask in subtasks)
    if all_completed:
        target = last
    elif any(subtask.column_id != first.pk for subtask in subtasks):
        target = _progress_column(task.board)
    else:
        target = first
    if task.column_id != target.pk or bool(task.completed_at) != all_completed:
        task.column = target
        task.completed_at = (task.completed_at or timezone.now()) if all_completed else None
        task.position = Task.objects.filter(column=target).count()
        task.save(update_fields=["column", "completed_at", "position", "updated_at"])


@login_required
def dashboard(request):
    _ensure_default_board(request.user)
    now = timezone.now()
    boards = list(Board.objects.filter(owner=request.user).annotate(
        task_count=Count("tasks", distinct=True),
        completed_count=Count("tasks", filter=Q(tasks__completed_at__isnull=False), distinct=True),
    ))
    columns_by_board = {}
    for column in Column.objects.filter(board__owner=request.user).order_by("position", "id"):
        columns_by_board.setdefault(column.board_id, []).append(column)
    all_tasks = list(
        Task.objects.filter(owner=request.user)
        .select_related("board", "column")
        .prefetch_related("activities")
    )
    board_progress = progress_by_board(all_tasks, columns_by_board)
    for board in boards:
        board.progress_percent = board_progress.get(board.pk, 0)
    tasks = Task.objects.filter(owner=request.user).select_related("board", "column")
    pending = tasks.filter(completed_at__isnull=True).annotate(
        activity_count=Count("activities", distinct=True),
        activity_completed=Count("activities", filter=Q(activities__completed=True), distinct=True),
    )
    overdue = pending.filter(due_at__lt=now).order_by("due_at")
    due_soon = pending.filter(due_at__gte=now, due_at__lte=now + timedelta(hours=48)).order_by("due_at")
    pending_preview = pending.order_by(F("due_at").asc(nulls_last=True), "-priority", "created_at")[:8]
    totals = tasks.aggregate(total=Count("id"), completed=Count("id", filter=Q(completed_at__isnull=False)))
    total_tasks = totals["total"] or 0
    completed_tasks = totals["completed"] or 0
    progress_percent = round(sum(task.progress_percent for task in all_tasks) / total_tasks) if total_tasks else 0
    return render(request, "tasks/overview.html", {
        "boards": boards,
        "overdue": overdue[:5], "overdue_count": overdue.count(),
        "due_soon": due_soon[:5], "due_soon_count": due_soon.count(),
        "pending_preview": pending_preview, "pending_count": pending.count(),
        "total_tasks": total_tasks, "completed_tasks": completed_tasks,
        "progress_percent": progress_percent, "now": now,
    })


@login_required
def board_detail(request, pk):
    board = get_object_or_404(Board, pk=pk, owner=request.user)
    boards = Board.objects.filter(owner=request.user).annotate(task_count=Count("tasks"))
    columns = list(board.columns.all())
    tasks = list(
        Task.objects.filter(owner=request.user, board=board)
        .select_related("column").prefetch_related("activities__column")
    )
    query = request.GET.get("q", "").strip()
    task_rows = []
    progress_values = []
    for task in tasks:
        subtasks = list(task.activities.all())
        for subtask in subtasks:
            subtask.cells = [{"column": column, "active": subtask.column_id == column.pk} for column in columns]
        task.cells = [{"column": column, "active": task.column_id == column.pk} for column in columns]
        task.subtask_rows = subtasks
        task.progress_percent = task_progress(task, columns, subtasks)
        progress_values.append(task.progress_percent)
        if not query or query.casefold() in task.title.casefold() or query.casefold() in task.description.casefold() or any(query.casefold() in subtask.title.casefold() for subtask in subtasks):
            task_rows.append(task)
    return render(request, "tasks/dashboard.html", {
        "boards": boards, "board": board, "columns": columns, "task_rows": task_rows,
        "board_progress": round(sum(progress_values) / len(progress_values)) if progress_values else 0,
        "board_task_count": len(tasks),
        "board_completed_count": sum(bool(task.completed_at) for task in tasks),
        "query": query,
    })


@login_required
def task_create(request):
    default_board = _ensure_default_board(request.user)
    initial = {"board": request.GET.get("tablero") or default_board.pk}
    form = TaskForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.column = _first_column(task.board)
        if task.column is None:
            form.add_error("board", "El tablero no tiene estados configurados.")
            return render(request, "tasks/form.html", {"form": form, "title": "Nueva tarea", "task_form": True})
        task.position = Task.objects.filter(column=task.column).count()
        task.full_clean()
        task.save()
        messages.success(request, "Tarea creada.")
        return redirect("board_detail", pk=task.board_id)
    return render(request, "tasks/form.html", {"form": form, "title": "Nueva tarea", "task_form": True})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    original_board_id = task.board_id
    form = TaskForm(request.POST or None, instance=task, user=request.user)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        if task.board_id != original_board_id:
            task.column = _first_column(task.board)
            if task.column is None:
                form.add_error("board", "El tablero no tiene estados configurados.")
                return render(request, "tasks/form.html", {"form": form, "title": "Editar tarea", "task": task, "task_form": True})
            task.position = Task.objects.filter(column=task.column).count()
            task.completed_at = None
        task.full_clean()
        task.save()
        messages.success(request, "Tarea actualizada.")
        return redirect("board_detail", pk=task.board_id)
    return render(request, "tasks/form.html", {"form": form, "title": "Editar tarea", "task": task, "task_form": True})


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    board_id = task.board_id
    task.delete()
    messages.success(request, "Tarea eliminada.")
    return redirect("board_detail", pk=board_id)


@login_required
@require_POST
def task_move(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    try:
        payload = json.loads(request.body) if request.content_type == "application/json" else request.POST
        column = Column.objects.get(pk=payload["column_id"], board=task.board, board__owner=request.user)
        position = max(0, int(payload.get("position", 0)))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, Column.DoesNotExist):
        if request.content_type != "application/json":
            messages.error(request, "Movimiento no válido.")
            return redirect("board_detail", pk=task.board_id)
        return JsonResponse({"error": "Movimiento no válido."}, status=400)
    completed_column = _completed_column(task.board)
    destination_is_completed = column.pk == completed_column.pk
    if task.activities.exists():
        if request.content_type != "application/json":
            messages.error(request, "Mueve las subtareas para cambiar el estado de esta tarea.")
            return redirect("board_detail", pk=task.board_id)
        return JsonResponse({"error": "Mueve las subtareas; el estado de la tarea se actualiza automáticamente."}, status=400)
    task.column = column
    task.position = position
    if destination_is_completed and not task.completed_at:
        task.completed_at = timezone.now()
    elif not destination_is_completed:
        task.completed_at = None
    task.save(update_fields=["column", "position", "completed_at", "updated_at"])
    if request.content_type != "application/json":
        return redirect("board_detail", pk=task.board_id)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def activity_move(request, pk):
    activity = get_object_or_404(Activity.objects.select_related("task__board"), pk=pk, task__owner=request.user)
    try:
        payload = json.loads(request.body) if request.content_type == "application/json" else request.POST
        column = Column.objects.get(pk=payload["column_id"], board_id=activity.task.board_id)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, Column.DoesNotExist):
        if request.content_type != "application/json":
            messages.error(request, "Estado no válido.")
            return redirect("board_detail", pk=activity.task.board_id)
        return JsonResponse({"error": "Estado no válido."}, status=400)
    with transaction.atomic():
        activity.column = column
        activity.completed = column.pk == _completed_column(activity.task.board).pk
        activity.save(update_fields=["column", "completed"])
        _sync_task_from_subtasks(activity.task)
    if request.content_type != "application/json":
        return redirect("board_detail", pk=activity.task.board_id)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if task.activities.exists():
        messages.info(request, "Esta tarea se completa al terminar todas sus subtareas.")
        return redirect("task_detail", pk=task.pk)
    if task.completed_at:
        task.column = _first_column(task.board)
        task.completed_at = None
    else:
        task.column = _completed_column(task.board)
        task.completed_at = timezone.now()
    if task.column is None:
        messages.error(request, "La lista no tiene estados configurados.")
    else:
        task.position = Task.objects.filter(column=task.column).count()
        task.save(update_fields=["column", "completed_at", "position", "updated_at"])
    return redirect("dashboard")


@login_required
def board_create(request):
    form = BoardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            board = form.save(commit=False)
            board.owner = request.user
            board.save()
            Column.objects.bulk_create([
                Column(board=board, name="Pendiente", position=0, color="#64748b"),
                Column(board=board, name="En progreso", position=1, color="#f59e0b"),
                Column(board=board, name="Completado", position=2, color="#10b981"),
            ])
        messages.success(request, "Lista creada.")
        return redirect("board_detail", pk=board.id)
    return render(request, "tasks/form.html", {"form": form, "title": "Nueva lista"})


@login_required
def notification_preferences(request):
    preferences, _ = NotificationSettings.objects.get_or_create(user=request.user)
    form = NotificationSettingsForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Preferencias guardadas.")
        return redirect("notification_preferences")
    return render(request, "tasks/form.html", {"form": form, "title": "Mis notificaciones"})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        Task.objects.select_related("board", "column").prefetch_related("activities"),
        pk=pk, owner=request.user,
    )
    form = ActivityForm()
    completed = task.activities.filter(completed=True).count()
    total = task.activities.count()
    return render(request, "tasks/task_detail.html", {
        "task": task, "activity_form": form, "activity_total": total,
        "activity_completed": completed,
    })


@login_required
@require_POST
def activity_create(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk, owner=request.user)
    form = ActivityForm(request.POST)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.task = task
        activity.position = task.activities.count()
        activity.save()
        _sync_task_from_subtasks(task)
    else:
        messages.error(request, "Escribe un nombre para la actividad.")
    return redirect("task_detail", pk=task.pk)


@login_required
@require_POST
def activity_toggle(request, pk):
    activity = get_object_or_404(Activity, pk=pk, task__owner=request.user)
    with transaction.atomic():
        activity.column = _first_column(activity.task.board) if activity.completed else _completed_column(activity.task.board)
        activity.completed = not activity.completed
        activity.save(update_fields=["column", "completed"])
        _sync_task_from_subtasks(activity.task)
    if request.POST.get("return_to") == "board":
        return redirect("board_detail", pk=activity.task.board_id)
    return redirect("task_detail", pk=activity.task_id)


@login_required
@require_POST
def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk, task__owner=request.user)
    task_id = activity.task_id
    task = activity.task
    with transaction.atomic():
        activity.delete()
        _sync_task_from_subtasks(task)
    return redirect("task_detail", pk=task_id)
