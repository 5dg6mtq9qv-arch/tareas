from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tasks", "0005_backfill_activity_columns")]

    operations = [
        migrations.AlterField(
            model_name="activity",
            name="column",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="activities",
                to="tasks.column",
                verbose_name="estado",
            ),
        ),
    ]
