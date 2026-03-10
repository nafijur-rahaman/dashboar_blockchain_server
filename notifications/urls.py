from django.urls import path
from .views import NotificationsListAPI, NotificationMarkReadAPI, NotificationMarkAllReadAPI


urlpatterns = [
    path("", NotificationsListAPI.as_view(), name="notifications-list"),
    path("read/<int:pk>/", NotificationMarkReadAPI.as_view(), name="notification-read"),
    path("read-all/", NotificationMarkAllReadAPI.as_view(), name="notification-read-all"),
]
