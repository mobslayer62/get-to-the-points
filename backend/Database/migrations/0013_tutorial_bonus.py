from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Database", "0012_gacha"),
    ]

    operations = [
        migrations.AddField(
            model_name="useractivity",
            name="tutorial_bonus_claimed",
            field=models.BooleanField(default=False),
        ),
    ]
