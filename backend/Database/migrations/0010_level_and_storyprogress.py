import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Database", "0009_run_only_effects"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="useractivity",
            name="level",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.CreateModel(
            name="StoryProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chapter_id", models.CharField(max_length=50)),
                ("completed_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_progress", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "chapter_id"), name="unique_chapter_per_user")],
            },
        ),
    ]
