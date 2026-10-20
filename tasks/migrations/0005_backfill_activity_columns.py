from django.db import migrations


def set_activity_columns(apps, schema_editor):
    Activity = apps.get_model("tasks", "Activity")
    Column = apps.get_model("tasks", "Column")
    for activity in Activity.objects.select_related("task").filter(column__isnull=True).iterator():
        columns = Column.objects.filter(board_id=activity.task.board_id).order_by("position", "id")
        column = columns.last() if activity.completed else columns.first()
        if column:
            Activity.objects.filter(pk=activity.pk).update(column_id=column.pk)


class Migration(migrations.Migration):
    dependencies = [("tasks", "0004_activity_column")]

    operations = [migrations.RunPython(set_activity_columns, migrations.RunPython.noop)]
