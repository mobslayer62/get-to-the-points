from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserActivity, WalkingSession
from .serializers import (
    FinishSessionSerializer,
    GroupSerializer,
    RegisterSerializer,
    UserSerializer,
    WalkingSessionSerializer,
)
from .utils import convert_distance_to_points


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----- Accounts -----

class RegisterView(APIView):
    """POST {username, password} -> {token, username}"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "username": user.username},
            status=status.HTTP_201_CREATED,
        )


class LoginView(ObtainAuthToken):
    """POST {username, password} -> {token, username}"""

    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        UserActivity.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class LogoutView(APIView):
    """POST -> deletes the current token so it can't be reused."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----- Activity -----

class FinishSessionView(APIView):
    """
    POST {session_id, distance, steps, duration_seconds}

    Sending the same session_id twice never awards points twice, so the app
    can safely retry if the network drops.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FinishSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        distance = data["distance"]
        points = convert_distance_to_points(distance)

        with transaction.atomic():
            UserActivity.objects.get_or_create(user=request.user)
            activity = UserActivity.objects.select_for_update().get(
                user=request.user
            )

            session, created = WalkingSession.objects.get_or_create(
                session_id=data["session_id"],
                defaults={
                    "user": request.user,
                    "distance": distance,
                    "steps": data["steps"],
                    "duration_seconds": data["duration_seconds"],
                    "points_earned": points,
                },
            )

            if not created:
                if session.user_id != request.user.id:
                    return Response(
                        {"error": "Invalid session"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                activity.total_distance += distance
                activity.total_steps += data["steps"]
                activity.total_points += points
                activity.save()

        return Response({
            "already_processed": not created,
            "session_distance": str(session.distance),
            "points_earned": session.points_earned,
            "total_distance": str(activity.total_distance),
            "total_points": activity.total_points,
        })


class ActivityHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activity = UserActivity.objects.filter(user=request.user).first()
        sessions = WalkingSession.objects.filter(user=request.user).order_by("-id")

        return Response({
            "total_distance": str(activity.total_distance) if activity else "0",
            "total_points": activity.total_points if activity else 0,
            "sessions": WalkingSessionSerializer(sessions, many=True).data,
        })


class PlayerStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activity = UserActivity.objects.filter(user=request.user).first()
        sessions = WalkingSession.objects.filter(user=request.user)

        session_count = sessions.count()
        total_distance = activity.total_distance if activity else Decimal("0")
        total_points = activity.total_points if activity else 0

        best = sessions.order_by("-distance").first()

        return Response({
            "username": request.user.username,
            "total_distance": str(total_distance),
            "total_points": total_points,
            "sessions_completed": session_count,
            "average_distance": (
                str(round(total_distance / session_count, 2)) if session_count else "0"
            ),
            "longest_session": str(best.distance) if best else "0",
        })
