from django.contrib.auth.models import Group, User
from rest_framework import serializers
from .models import UserActivity, WalkingSession, UserCard


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


# Individual walking session history
class WalkingSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(required=True)
    
    class Meta:
        model = WalkingSession
        fields = [
            "session_id",
            "distance",
            "steps",
            "points_earned",
            "created_at"
        ]
        read_only_fields = [
            "points_earned",
            "created_at"
        ]


# Player's accumulated statistics
class UserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = [
            "total_distance",
            "total_steps",
            "total_points"
        ]


class UserCardSerializer(serializers.ModelSerializer):
    card_id = serializers.IntegerField(source="card.id", read_only=True)
    name = serializers.CharField(source="card.name", read_only=True)
    description = serializers.CharField(source="card.description", read_only=True)
    rarity = serializers.CharField(source="card.rarity", read_only=True)
    image_url = serializers.CharField(source="card.image_url", read_only=True)

    class Meta:
        model = UserCard
        fields = [
            "card_id",
            "name",
            "description",
            "rarity",
            "image_url",
            "quantity",
            "first_obtained_at",
        ]
