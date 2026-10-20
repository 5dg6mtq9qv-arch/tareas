from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Activity, Board, Column, NotificationConfiguration, NotificationLog, NotificationSettings, Task


class UserIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", password="test-pass-123")
        self.bob = User.objects.create_user("bob", password="test-pass-123")
        self.alice_board = Board.objects.create(owner=self.alice, name="Alice")
        self.alice_column = Column.objects.create(board=self.alice_board, name="Pendiente")
        self.task = Task.objects.create(owner=self.alice, board=self.alice_board, column=self.alice_column, title="Privada")

    def test_user_cannot_edit_another_users_task(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("task_edit", args=[self.task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_dashboard_only_lists_own_boards(self):
        Board.objects.create(owner=self.bob, name="Bob")
        self.client.force_login(self.bob)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "Alice")
        self.assertContains(response, "Bob")

    def test_user_cannot_move_another_users_task(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("task_move", args=[self.task.pk]),
            data='{"column_id": %s}' % self.alice_column.pk,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_new_task_always_starts_in_first_column(self):
        second = Column.objects.create(
            board=self.alice_board, name="En progreso", position=1
        )
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("task_create") + f"?tablero={self.alice_board.pk}&columna={second.pk}",
            {"board": self.alice_board.pk, "title": "Nueva tarea", "priority": "medium", "column": second.pk},
        )

        self.assertEqual(response.status_code, 302)
        created = Task.objects.get(title="Nueva tarea")
        self.assertEqual(created.column, self.alice_column)

    def test_user_cannot_toggle_another_users_activity(self):
        activity = Activity.objects.create(task=self.task, title="Paso privado")
        self.client.force_login(self.bob)

        response = self.client.post(reverse("activity_toggle", args=[activity.pk]))

        self.assertEqual(response.status_code, 404)
        activity.refresh_from_db()
        self.assertFalse(activity.completed)

    def test_activity_can_be_added_to_own_task(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("activity_create", args=[self.task.pk]), {"title": "Primer paso"}
        )

        self.assertRedirects(response, reverse("task_detail", args=[self.task.pk]))
        self.assertTrue(self.task.activities.filter(title="Primer paso").exists())

    def test_user_can_complete_own_task_from_dashboard(self):
        Column.objects.create(board=self.alice_board, name="Completado", position=2)
        self.client.force_login(self.alice)

        response = self.client.post(reverse("task_complete", args=[self.task.pk]))

        self.assertRedirects(response, reverse("dashboard"))
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.task.column.name, "Completado")

    def test_finishing_all_subtasks_completes_parent_task(self):
        Column.objects.create(board=self.alice_board, name="Completado", position=2)
        first = Activity.objects.create(task=self.task, title="Primera")
        Activity.objects.create(task=self.task, title="Segunda", completed=True)
        self.client.force_login(self.alice)

        self.client.post(reverse("activity_toggle", args=[first.pk]))

        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.task.column.name, "Completado")

    def test_unchecking_subtask_reopens_parent_task(self):
        completed_column = Column.objects.create(
            board=self.alice_board, name="Completado", position=2
        )
        self.task.column = completed_column
        self.task.completed_at = timezone.now()
        self.task.save()
        subtask = Activity.objects.create(task=self.task, title="Paso", completed=True)
        self.client.force_login(self.alice)

        self.client.post(reverse("activity_toggle", args=[subtask.pk]))

        self.task.refresh_from_db()
        self.assertIsNone(self.task.completed_at)
        self.assertEqual(self.task.column, self.alice_column)

    def test_board_shows_subtasks_and_can_toggle_them(self):
        Column.objects.create(board=self.alice_board, name="Completado", position=2)
        subtask = Activity.objects.create(task=self.task, title="Paso visible")
        self.client.force_login(self.alice)

        board_response = self.client.get(reverse("board_detail", args=[self.alice_board.pk]))
        toggle_response = self.client.post(
            reverse("activity_toggle", args=[subtask.pk]), {"return_to": "board"}
        )

        self.assertContains(board_response, "Paso visible")
        self.assertRedirects(toggle_response, reverse("board_detail", args=[self.alice_board.pk]))
        subtask.refresh_from_db()
        self.assertTrue(subtask.completed)

    def test_subtasks_move_independently_and_complete_parent(self):
        progress = Column.objects.create(board=self.alice_board, name="En progreso", position=1)
        done = Column.objects.create(board=self.alice_board, name="Completado", position=2)
        first = Activity.objects.create(task=self.task, title="Investigar")
        second = Activity.objects.create(task=self.task, title="Entregar")
        self.client.force_login(self.alice)

        response = self.client.post(reverse("activity_move", args=[first.pk]), {"column_id": progress.pk})
        self.assertRedirects(response, reverse("board_detail", args=[self.alice_board.pk]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(first.column, progress)
        self.assertEqual(second.column, self.alice_column)
        self.assertEqual(self.task.column, progress)
        self.assertIsNone(self.task.completed_at)

        self.client.post(reverse("activity_move", args=[first.pk]), {"column_id": done.pk})
        self.client.post(reverse("activity_move", args=[second.pk]), {"column_id": done.pk})
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, done)
        self.assertIsNotNone(self.task.completed_at)

        self.client.post(reverse("activity_move", args=[second.pk]), {"column_id": progress.pk})
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, progress)
        self.assertIsNone(self.task.completed_at)

    def test_subtask_cannot_move_to_another_users_column(self):
        subtask = Activity.objects.create(task=self.task, title="Privada")
        other_board = Board.objects.create(owner=self.bob, name="Otra")
        other_column = Column.objects.create(board=other_board, name="Pendiente")
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse("activity_move", args=[subtask.pk]),
            data='{"column_id": %s}' % other_column.pk,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        subtask.refresh_from_db()
        self.assertEqual(subtask.column, self.alice_column)


class ControlPanelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pass-123")
        self.regular = User.objects.create_user("normal", password="normal-pass-123")

    def test_regular_user_cannot_use_control_panel(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse("control_panel"))
        self.assertNotEqual(response.status_code, 200)

    def test_admin_can_create_user_and_configure_alerts(self):
        self.client.force_login(self.admin)
        created = self.client.post(reverse("managed_user_create"), {
            "username": "nuevo", "email": "nuevo@example.com",
            "password1": "ClaveSegura2026!", "password2": "ClaveSegura2026!",
        })
        self.assertRedirects(created, reverse("control_panel"))
        user = get_user_model().objects.get(username="nuevo")
        configured = self.client.post(reverse("managed_user_alerts", args=[user.pk]), {
            "email_enabled": "on", "telegram_enabled": "on",
            "telegram_chat_id": "123456", "reminder_minutes": 30,
        })
        self.assertRedirects(configured, reverse("control_panel"))
        self.assertTrue(NotificationSettings.objects.get(user=user).telegram_enabled)

    def test_blank_secret_fields_preserve_existing_credentials(self):
        NotificationConfiguration.objects.create(
            email_backend="django.core.mail.backends.smtp.EmailBackend",
            email_host="smtp.example.com", email_username="sender@example.com",
            email_password="smtp-secret", telegram_bot_token="bot-secret",
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("save_notification_config"), {
            "email_backend": "django.core.mail.backends.smtp.EmailBackend",
            "email_host": "new.example.com", "email_port": 587,
            "email_username": "sender@example.com", "email_password": "",
            "email_use_tls": "on", "default_from_email": "sender@example.com",
            "telegram_bot_token": "",
        })
        self.assertRedirects(response, reverse("control_panel"))
        config = NotificationConfiguration.objects.get()
        self.assertEqual(config.email_host, "new.example.com")
        self.assertEqual(config.email_password, "smtp-secret")
        self.assertEqual(config.telegram_bot_token, "bot-secret")


class DueAlertTests(TestCase):
    def test_email_alert_is_sent_only_once(self):
        user = get_user_model().objects.create_user(
            "maria", email="maria@example.com", password="test-pass-123"
        )
        board = Board.objects.create(owner=user, name="Estudio")
        column = Column.objects.create(board=board, name="Pendiente")
        task = Task.objects.create(
            owner=user,
            board=board,
            column=column,
            title="Entregar informe",
            due_at=timezone.now() + timedelta(minutes=30),
        )
        NotificationSettings.objects.create(user=user, email_enabled=True, reminder_minutes=60)

        call_command("send_due_alerts")
        call_command("send_due_alerts")

        self.assertEqual(NotificationLog.objects.filter(task=task, channel="email").count(), 1)
