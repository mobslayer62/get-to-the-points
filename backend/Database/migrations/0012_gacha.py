import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Database", "0011_seed_cards"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="useractivity",
            name="pulls_since_s",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="useractivity",
            name="total_pulls",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="GachaPull",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rarity", models.CharField(max_length=20)),
                ("was_pity", models.BooleanField(default=False)),
                ("pulled_at", models.DateTimeField(auto_now_add=True)),
                ("card", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="Database.card")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gacha_pulls", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
