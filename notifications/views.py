from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationsListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == "admin":
            qs = Notification.objects.filter(is_admin=True)
        else:
            qs = Notification.objects.filter(recipient=request.user)

        # unread count BEFORE slicing
        unread_count = qs.filter(is_read=False).count()

        # then slice after ordering
        notifications = qs.order_by("-created_at")[:50]

        serializer = NotificationSerializer(notifications, many=True)

        return Response({
            "notifications": serializer.data,
            "unread_count": unread_count,
        })

class NotificationMarkReadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role == "admin":
            Notification.objects.filter(id=pk, is_admin=True).update(is_read=True)
        else:
            Notification.objects.filter(id=pk, recipient=request.user).update(is_read=True)
        return Response({"message": "Notification marked as read"})


class NotificationMarkAllReadAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role == "admin":
            Notification.objects.filter(is_admin=True, is_read=False).update(is_read=True)
        else:
            Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All notifications marked as read"})
