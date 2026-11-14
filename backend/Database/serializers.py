from django.contrib.auth.models import Group, User
from rest_framework import serializers
from .models import UserActivity, WalkingSession


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
