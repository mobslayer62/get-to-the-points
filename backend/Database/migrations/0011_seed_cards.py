"""Seed the starting card catalog so every fresh database has the same cards.

Cards are matched by name (unique), so running this on a database that
already has them updates their stats instead of creating duplicates.
"""
from django.db import migrations

CARDS = [
    {
        "name": "EDU Building",
        "description": "Office of IBP and General Education hub!",
        "rarity": "A",
        "image_url": "https://drive.google.com/file/d/1VWX3w4lzRIzomFHZkW3qeVjWUSJDtENh/view?usp=sharing",
        "effect_type": "points_percent",
        "effect_value": 5,
        "special_threshold": 40,
        "special_type": "min_duration",
        "special_value": 50,
    },
    {
        "name": "Niu Pai (牛排)",
        "description": "NTHU's own dog!",
        "rarity": "S",
        "image_url": "https://drive.google.com/file/d/1hx4655cx6oo2ysTS4dZDXTjdmgLs-KF1/view?usp=sharing",
        "effect_type": "walk_points_percent",
        "effect_value": 40,
        "special_threshold": 1000,
        "special_type": "walk_distance",
        "special_value": 20,
    },
    {
        "name": "Library",
        "description": "Home to one of the 26 sculptures of \"The Thinker\"",
        "rarity": "A+",
        "image_url": "https://drive.google.com/file/d/1ukfKw7AgvtNBthX0UqFj81fGTM7JtQj5/view?usp=sharing",
        "effect_type": "points_percent",
        "effect_value": 20,
        "special_threshold": 5000,
        "special_type": "distance_milestone",
        "special_value": 20,
    },
    {
        "name": "General Building II",
        "description": "Where you come to study languages!",
        "rarity": "A+",
        "image_url": "https://drive.google.com/file/d/1hBNtV--Yp18Mg7rCOY4o2iVKFV62YadD/view?usp=sharing",
        "effect_type": "points_percent",
        "effect_value": 10,
        "special_threshold": 40,
        "special_type": "min_duration",
        "special_value": 75,
    },
    {
        "name": "Feng Yun (風雲)",
        "description": "Student activity area, Dining hall, Restaurant, and bookstore, all in one!",
        "rarity": "A+",
        "image_url": "https://drive.google.com/file/d/1xdWkoIayBcnrYj8MWLMC7X8sEJtcN3Zn/view?usp=sharing",
        "effect_type": "walk_points_percent",
        "effect_value": 25,
        "special_threshold": 1000,
        "special_type": "distance_milestone",
        "special_value": 15,
    },
    {
        "name": "NTHU Main Gate",
        "description": "Welcome to NTHU!",
        "rarity": "A",
        "image_url": "https://drive.google.com/file/d/120Vh07TVDC7aaG6T9uKfWwNZdzkU2-YD/view?usp=sharing",
        "effect_type": "points_percent",
        "effect_value": 5,
        "special_threshold": 20,
        "special_type": "min_duration",
        "special_value": 25,
    },
    {
        "name": "Grass Field",
        "description": "Location of NTHU Sports Day 2026",
        "rarity": "A",
        "image_url": "https://drive.google.com/file/d/1HrhCNSChC2uxjgawT3zdgjWX0UAUcWIx/view?usp=sharing",
        "effect_type": "run_points_percent",
        "effect_value": 10,
        "special_threshold": 5000,
        "special_type": "run_distance",
        "special_value": 40,
    },
    {
        "name": "Chemical Engineering Building",
        "description": "Features a sundial which can be used to read the time and look at the North Star",
        "rarity": "A",
        "image_url": "https://drive.google.com/file/d/1lLna6FGhcueF_ixEV84Ok89rKliO5JiV/view?usp=sharing",
        "effect_type": "run_points_percent",
        "effect_value": 15,
        "special_threshold": 1000,
        "special_type": "run_distance",
        "special_value": 5,
    },
    {
        "name": "Office of Global Affairs",
        "description": "Where international relationships are made",
        "rarity": "A",
        "image_url": "https://drive.google.com/file/d/16yYBEa27AJsKkcVJigTZ6gWa1SepAaZJ/view?usp=sharing",
        "effect_type": "walk_points_percent",
        "effect_value": 15,
        "special_threshold": 1000,
        "special_type": "walk_distance",
        "special_value": 5,
    },
    {
        "name": "XCB (小吃部)",
        "description": "Food court of NTHU",
        "rarity": "S",
        "image_url": "https://drive.google.com/file/d/1CfmWyH1fTmsoGxIIeOD33OamNEezg1hG/view?usp=sharing",
        "effect_type": "points_percent",
        "effect_value": 30,
        "special_threshold": 5000,
        "special_type": "distance_milestone",
        "special_value": 100,
    },
]


def seed_cards(apps, schema_editor):
    Card = apps.get_model("Database", "Card")
    for data in CARDS:
        fields = dict(data)
        name = fields.pop("name")
        Card.objects.update_or_create(name=name, defaults=fields)


def unseed_cards(apps, schema_editor):
    Card = apps.get_model("Database", "Card")
    Card.objects.filter(name__in=[c["name"] for c in CARDS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Database", "0010_level_and_storyprogress"),
    ]

    operations = [
        migrations.RunPython(seed_cards, unseed_cards),
    ]
