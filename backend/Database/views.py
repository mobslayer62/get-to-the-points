from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets

from .serializers import GroupSerializer, UserSerializer


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

from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import UserActivity, WalkingSession
from .utils import convert_distance_to_points


class FinishSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:
            session_id = request.data["session_id"]
            distance = Decimal(str(request.data["distance"]))

            if not distance.is_finite() or distance < 0:
                raise ValueError()

        except (KeyError, InvalidOperation, ValueError, TypeError):
            return Response(
                {"error": "Invalid session data"},
                status=400
            )

        points = convert_distance_to_points(distance)

        with transaction.atomic():

            activity, _ = UserActivity.objects.get_or_create(
                user=request.user
            )

            activity = UserActivity.objects.select_for_update().get(
                user=request.user
            )

            session, created = WalkingSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    "user": request.user,
                    "distance": distance,
                    "points_earned": points
                }
            )

            if not created:
                if session.user_id != request.user.id:
                    return Response(
                        {"error": "Invalid session"},
                        status=403
                    )

                return Response({
                    "message": "Session already processed",
                    "points_earned": session.points_earned
                })

            activity.total_distance += distance
            activity.total_points += points
            activity.save()

        return Response({
            "session_distance": str(distance),
            "points_earned": points,
            "total_distance": str(activity.total_distance),
            "total_points": activity.total_points

        })
class ActivityHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activity = UserActivity.objects.filter(user=request.user).first()

        sessions = (
            WalkingSession.objects
            .filter(user=request.user)
            .order_by("-id")
        )

        return Response({
            "total_distance": str(activity.total_distance) if activity else "0",
            "total_points": activity.total_points if activity else 0,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "distance": str(s.distance),
                    "points_earned": s.points_earned,
                }
                for s in sessions
            ],
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
            "average_distance": str(total_distance / session_count) if session_count else "0",
            "longest_session": str(best.distance) if best else "0",
        })

class CardStorageView(APIView):
    """GET the logged-in user's card collection."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import UserCard
        from .serializers import UserCardSerializer

        cards = (
            UserCard.objects
            .filter(user=request.user)
            .select_related("card")
            .order_by("card__name")
        )

        return Response({
            "unique_cards": cards.count(),
            "total_cards": sum(c.quantity for c in cards),
            "cards": UserCardSerializer(cards, many=True).data,
        })
