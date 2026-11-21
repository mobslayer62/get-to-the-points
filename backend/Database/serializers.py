from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import EquippedCard, UserActivity, UserCard, WalkingSession
from .utils import find_session_problem


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


# ----- Accounts -----

class RegisterSerializer(serializers.Serializer):
    username = serializers.RegexField(
        r"^[\w.@+-]+$",
        min_length=3,
        max_length=150,
        error_messages={
            "invalid": "Username may only contain letters, numbers and @ . + - _",
        },
    )
    password = serializers.CharField(write_only=True, max_length=128)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, data):
        # Run Django's password validators (length, common passwords, etc.)
        candidate = User(username=data["username"])
        try:
            validate_password(data["password"], user=candidate)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )
        UserActivity.objects.create(user=user)

        from .onboarding import give_starter_card
        give_starter_card(user)
        return user


# ----- Activity -----

class FinishSessionSerializer(serializers.Serializer):
    """Validates a completed run sent by the app."""

    session_id = serializers.UUIDField()
    distance = serializers.DecimalField(
        max_digits=9, decimal_places=2, min_value=Decimal("0")
    )
    steps = serializers.IntegerField(min_value=0, required=False, default=0)
    duration_seconds = serializers.IntegerField(min_value=0, required=False, default=0)

    def validate(self, data):
        problem = find_session_problem(data["distance"], data["duration_seconds"])
        if problem:
            raise serializers.ValidationError({"error": problem})
        return data


class StartSessionSerializer(serializers.Serializer):
    """The app picks the session id when the run starts and reuses it at finish."""

    session_id = serializers.UUIDField()


# Individual walking session history
class WalkingSessionSerializer(serializers.ModelSerializer):
    equipped_card_ids = serializers.PrimaryKeyRelatedField(
        source="equipped_cards", many=True, read_only=True
    )

    class Meta:
        model = WalkingSession
        fields = [
            "session_id",
            "distance",
            "steps",
            "duration_seconds",
            "points_earned",
            "bonus_points",
            "equipped_card_ids",
            "created_at",
        ]
        read_only_fields = fields


# Player's accumulated statistics
class UserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = [
            "total_distance",
            "total_steps",
            "total_points",
        ]


class UserCardSerializer(serializers.ModelSerializer):
    card_id = serializers.IntegerField(source="card.id", read_only=True)
    name = serializers.CharField(source="card.name", read_only=True)
    description = serializers.CharField(source="card.description", read_only=True)
    rarity = serializers.CharField(source="card.rarity", read_only=True)
    image_url = serializers.CharField(source="card.image_url", read_only=True)
    effect_type = serializers.CharField(source="card.effect_type", read_only=True)
    effect_value = serializers.IntegerField(source="card.effect_value", read_only=True)
    special_type = serializers.CharField(source="card.special_type", read_only=True)
    special_value = serializers.IntegerField(source="card.special_value", read_only=True)
    special_threshold = serializers.IntegerField(
        source="card.special_threshold", read_only=True
    )

    class Meta:
        model = UserCard
        fields = [
            "card_id",
            "name",
            "description",
            "rarity",
            "image_url",
            "effect_type",
            "effect_value",
            "special_type",
            "special_value",
            "special_threshold",
            "quantity",
            "first_obtained_at",
        ]


# ----- Card loadout -----

class EquippedCardSerializer(serializers.ModelSerializer):
    card_id = serializers.IntegerField(source="card.id", read_only=True)
    name = serializers.CharField(source="card.name", read_only=True)
    description = serializers.CharField(source="card.description", read_only=True)
    rarity = serializers.CharField(source="card.rarity", read_only=True)
    image_url = serializers.CharField(source="card.image_url", read_only=True)
    effect_type = serializers.CharField(source="card.effect_type", read_only=True)
    effect_value = serializers.IntegerField(source="card.effect_value", read_only=True)
    special_type = serializers.CharField(source="card.special_type", read_only=True)
    special_value = serializers.IntegerField(source="card.special_value", read_only=True)
    special_threshold = serializers.IntegerField(
        source="card.special_threshold", read_only=True
    )

    class Meta:
        model = EquippedCard
        fields = [
            "slot", "card_id", "name", "description", "rarity", "image_url",
            "effect_type", "effect_value",
            "special_type", "special_value", "special_threshold",
        ]


class SetEquippedCardsSerializer(serializers.Serializer):
    """
    PUT {"card_ids": [3, 7, 1]} replaces the whole loadout.
    Order = slot order. 0..4 cards, no duplicates, must be owned.
    """

    card_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        max_length=EquippedCard.MAX_SLOTS,
        error_messages={
            "max_length": f"You can equip at most {EquippedCard.MAX_SLOTS} cards.",
        },
    )

    def validate_card_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("You can't equip the same card twice.")

        user = self.context["request"].user
        owned = set(
            UserCard.objects
            .filter(user=user, card_id__in=value)
            .values_list("card_id", flat=True)
        )
        missing = [cid for cid in value if cid not in owned]
        if missing:
            raise serializers.ValidationError(
                f"You don't own card(s): {', '.join(map(str, missing))}."
            )
        return value
