from rest_framework.authtoken.views import obtain_auth_token
from django.urls import path, include
from rest_framework import routers

from .views import (
    UserViewSet,
    GroupViewSet,
    FinishSessionView,
    ActivityHistoryView,
    PlayerStatsView,
    CardStorageView,
)

router = routers.DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"groups", GroupViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("finish-session/", FinishSessionView.as_view(), name="finish-session"),
    path("activity-history/", ActivityHistoryView.as_view(), name="activity-history"),
    path("player-stats/", PlayerStatsView.as_view(), name="player-stats"),
    path("card-storage/", CardStorageView.as_view(), name="card-storage"),
    path("login/", obtain_auth_token, name="api-login"),
]
