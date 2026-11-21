from django.urls import path, include
from rest_framework import routers

from .views import (
    UserViewSet,
    GroupViewSet,
    RegisterView,
    LoginView,
    LogoutView,
    StartSessionView,
    FinishSessionView,
    ActivityHistoryView,
    PlayerStatsView,
    CardStorageView,
    HomeSummaryView,
    EquippedCardsView,
    LevelView,
    LevelUpView,
    StoryListView,
    StoryChapterView,
    StoryCompleteView,
    GachaInfoView,
    GachaPullView,
    TutorialView,
    TutorialRunBonusView,
)

router = routers.DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"groups", GroupViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("register/", RegisterView.as_view(), name="api-register"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("logout/", LogoutView.as_view(), name="api-logout"),
    path("start-session/", StartSessionView.as_view(), name="start-session"),
    path("finish-session/", FinishSessionView.as_view(), name="finish-session"),
    path("activity-history/", ActivityHistoryView.as_view(), name="activity-history"),
    path("player-stats/", PlayerStatsView.as_view(), name="player-stats"),
    path("card-storage/", CardStorageView.as_view(), name="card-storage"),
    path("equipped-cards/", EquippedCardsView.as_view(), name="equipped-cards"),
    path("home/", HomeSummaryView.as_view(), name="home-summary"),
    path("level/", LevelView.as_view(), name="level"),
    path("level/up/", LevelUpView.as_view(), name="level-up"),
    path("story/", StoryListView.as_view(), name="story-list"),
    path("story/<slug:chapter_id>/", StoryChapterView.as_view(), name="story-chapter"),
    path("story/<slug:chapter_id>/complete/", StoryCompleteView.as_view(), name="story-complete"),
    path("gacha/", GachaInfoView.as_view(), name="gacha"),
    path("gacha/pull/", GachaPullView.as_view(), name="gacha-pull"),
    path("tutorial/", TutorialView.as_view(), name="tutorial"),
    path("tutorial/run-bonus/", TutorialRunBonusView.as_view(), name="tutorial-run-bonus"),
]
