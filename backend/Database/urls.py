from django.urls import path, include
from rest_framework import routers

from .views import (
    UserViewSet,
    GroupViewSet,
    RegisterView,
    LoginView,
    LogoutView,
    FinishSessionView,
    ActivityHistoryView,
    PlayerStatsView,
)

router = routers.DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"groups", GroupViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("register/", RegisterView.as_view(), name="api-register"),
    path("login/", LoginView.as_view(), name="api-login"),
    path("logout/", LogoutView.as_view(), name="api-logout"),
    path("finish-session/", FinishSessionView.as_view(), name="finish-session"),
    path("activity-history/", ActivityHistoryView.as_view(), name="activity-history"),
    path("player-stats/", PlayerStatsView.as_view(), name="player-stats"),
]
