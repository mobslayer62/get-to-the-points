from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EquippedCard, SessionStart, UserActivity, WalkingSession
from .serializers import (
    EquippedCardSerializer,
    FinishSessionSerializer,
    SetEquippedCardsSerializer,
    StartSessionSerializer,
    GroupSerializer,
    RegisterSerializer,
    UserSerializer,
    WalkingSessionSerializer,
)
from .utils import (
    calculate_card_bonuses,
    convert_distance_to_points,
    remove_unowned_equipped_cards,
)


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

class StartSessionView(APIView):
    """
    POST {session_id} when the player taps Start.

    Locks in the player's equipped cards for this run. Safe to retry with
    the same session_id: the loadout is only captured the first time.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data["session_id"]

        if WalkingSession.objects.filter(session_id=session_id).exists():
            return Response(
                {"error": "This run has already been finished."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            start, created = SessionStart.objects.get_or_create(
                session_id=session_id,
                defaults={"user": request.user},
            )
            if start.user_id != request.user.id:
                return Response(
                    {"error": "Invalid session"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if created:
                # Never lock in a card the player no longer owns.
                remove_unowned_equipped_cards(request.user)
                start.equipped_cards.set(
                    EquippedCard.objects
                    .filter(user=request.user)
                    .values_list("card_id", flat=True)
                )

        return Response({
            "session_id": str(start.session_id),
            "started_at": start.started_at.isoformat(),
            "equipped_card_ids": list(
                start.equipped_cards.order_by("id").values_list("id", flat=True)
            ),
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class FinishSessionView(APIView):
    """
    POST {session_id, distance, steps, duration_seconds}

    The session_id must come from a run started with start-session.
    Sending the same session_id twice never awards points twice, so the app
    can safely retry if the network drops.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FinishSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        distance = data["distance"]
        base_points = convert_distance_to_points(distance)

        with transaction.atomic():
            UserActivity.objects.get_or_create(user=request.user)
            activity = UserActivity.objects.select_for_update().get(
                user=request.user
            )

            session = WalkingSession.objects.filter(
                session_id=data["session_id"]
            ).first()

            if session is not None:
                # Retry of a run that was already saved.
                if session.user_id != request.user.id:
                    return Response(
                        {"error": "Invalid session"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                created = False
            else:
                start = (
                    SessionStart.objects
                    .select_for_update()
                    .filter(session_id=data["session_id"])
                    .first()
                )
                if start is None:
                    return Response(
                        {"error": "This run was never started."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if start.user_id != request.user.id:
                    return Response(
                        {"error": "Invalid session"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Use the cards locked in at the start, not the current loadout.
                cards = list(start.equipped_cards.order_by("id"))

                # Duration-based specials can't be unlocked by a run that
                # claims to be longer than the time since it was started.
                elapsed = int((timezone.now() - start.started_at).total_seconds())
                bonus_points, card_bonuses = calculate_card_bonuses(
                    base_points,
                    cards,
                    distance=distance,
                    duration_seconds=min(data["duration_seconds"], max(elapsed, 0)),
                    previous_total_distance=activity.total_distance,
                )

                session = WalkingSession.objects.create(
                    session_id=data["session_id"],
                    user=request.user,
                    distance=distance,
                    steps=data["steps"],
                    duration_seconds=data["duration_seconds"],
                    points_earned=base_points + bonus_points,
                    bonus_points=bonus_points,
                    card_bonus_breakdown=card_bonuses,
                )
                created = True

                session.equipped_cards.set(cards)
                start.delete()

                activity.total_distance += distance
                activity.total_steps += data["steps"]
                activity.total_points += session.points_earned
                activity.save()

        return Response({
            "already_processed": not created,
            "session_distance": str(session.distance),
            "base_points": session.points_earned - session.bonus_points,
            "bonus_points": session.bonus_points,
            # Saved with the run, so retries show exactly what was awarded.
            "card_bonuses": session.card_bonus_breakdown,
            "points_earned": session.points_earned,
            "equipped_card_ids": list(
                session.equipped_cards.order_by("id").values_list("id", flat=True)
            ),
            "total_distance": str(activity.total_distance),
            "total_points": activity.total_points,
        })


class ActivityHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activity = UserActivity.objects.filter(user=request.user).first()
        sessions = (
            WalkingSession.objects
            .filter(user=request.user)
            .prefetch_related("equipped_cards")
            .order_by("-id")
        )

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


class EquippedCardsView(APIView):
    """
    GET -> the player's current loadout (up to 4 unique cards).
    PUT {"card_ids": [..]} -> replace the loadout; list order = slot order.

    Whatever is equipped when a run starts is locked in for that run
    (see StartSessionView). Cards the player no longer owns are removed
    automatically and the remaining cards move up to fill the gaps.
    """

    permission_classes = [IsAuthenticated]

    def _response(self, user):
        remove_unowned_equipped_cards(user)
        equipped = (
            EquippedCard.objects
            .filter(user=user)
            .select_related("card")
            .order_by("slot")
        )
        return Response({
            "max_slots": EquippedCard.MAX_SLOTS,
            "cards": EquippedCardSerializer(equipped, many=True).data,
        })

    def get(self, request):
        return self._response(request.user)

    def put(self, request):
        serializer = SetEquippedCardsSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        card_ids = serializer.validated_data["card_ids"]

        with transaction.atomic():
            EquippedCard.objects.filter(user=request.user).delete()
            EquippedCard.objects.bulk_create([
                EquippedCard(user=request.user, card_id=card_id, slot=i)
                for i, card_id in enumerate(card_ids, start=1)
            ])

        return self._response(request.user)


class HomeSummaryView(APIView):
    """GET everything the main menu needs in one request."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .utils import build_home_summary

        return Response(build_home_summary(request.user))


# ----- Levels and story -----

class LevelView(APIView):
    """
    GET the player's level, points, the cost and rewards of the next level,
    plus the full list of levels for the level tab.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .progression import get_activity, level_summary, levels_overview

        activity = get_activity(request.user)
        return Response({
            **level_summary(activity),
            "levels": levels_overview(activity),
        })


class LevelUpView(APIView):
    """POST: spend points to go up one level."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .progression import ProgressionError, level_summary, level_up

        try:
            activity, spent, unlocked = level_up(request.user)
        except ProgressionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "points_spent": spent,
            "unlocked_chapters": [
                {"id": c["id"], "title": c["title"]} for c in unlocked
            ],
            "level": level_summary(activity),
        })


class StoryListView(APIView):
    """GET every chapter with its locked / completed state."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .progression import level_summary, story_overview

        activity, chapters = story_overview(request.user)
        return Response({
            "level": level_summary(activity),
            "chapters": chapters,
        })


class StoryChapterView(APIView):
    """GET one chapter's cast and dialogue (only if unlocked)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, chapter_id):
        from .progression import ProgressionError, chapter_for_reader, readable_chapter

        try:
            chapter = readable_chapter(request.user, chapter_id)
        except KeyError:
            return Response({"error": "Chapter not found."}, status=status.HTTP_404_NOT_FOUND)
        except ProgressionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(chapter_for_reader(chapter))


class StoryCompleteView(APIView):
    """POST when the player reaches the last line of a chapter."""

    permission_classes = [IsAuthenticated]

    def post(self, request, chapter_id):
        from .progression import ProgressionError, complete_chapter

        try:
            first_time = complete_chapter(request.user, chapter_id)
        except KeyError:
            return Response({"error": "Chapter not found."}, status=status.HTTP_404_NOT_FOUND)
        except ProgressionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        from .onboarding import grant_chapter_rewards

        rewards = grant_chapter_rewards(request.user, chapter_id) if first_time else []
        return Response({
            "completed": True,
            "first_time": first_time,
            "rewards": rewards,
        })


# ----- Gacha -----

class GachaInfoView(APIView):
    """GET costs, rates, the player's pity counter and the card pool."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .gacha import gacha_info
        from .progression import get_activity

        return Response(gacha_info(get_activity(request.user)))


class GachaPullView(APIView):
    """POST {"count": 1 | 10}: spend points and pull cards."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .gacha import GachaError, gacha_info, pull

        try:
            count = int(request.data.get("count", 1))
        except (TypeError, ValueError):
            return Response({"error": "count must be a number."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            results, activity = pull(request.user, count)
        except GachaError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "results": results,
            "gacha": gacha_info(activity),
        })


# ----- Tutorial -----

class TutorialView(APIView):
    """GET the tutorial steps, filled in for this player."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .onboarding import tutorial_for

        return Response(tutorial_for(request.user))


class TutorialRunBonusView(APIView):
    """POST once at the tutorial's run step (run finished or skipped)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .onboarding import claim_tutorial_run_bonus

        awarded, activity = claim_tutorial_run_bonus(request.user)
        return Response({
            "awarded": awarded,
            "total_points": activity.total_points,
        })
