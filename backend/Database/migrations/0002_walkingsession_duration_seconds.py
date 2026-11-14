from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Database", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="walkingsession",
            name="duration_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
