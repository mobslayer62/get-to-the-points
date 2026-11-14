from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import UserActivity, WalkingSession
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


# Individual walking session history
class WalkingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalkingSession
        fields = [
            "session_id",
            "distance",
            "steps",
            "duration_seconds",
            "points_earned",
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
