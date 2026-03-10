from .models import Notification


def create_admin_notification(title, message, notif_type="", data=None):
    return Notification.objects.create(
        is_admin=True,
        title=title,
        message=message,
        notif_type=notif_type,
        data=data or {},
    )


def create_user_notification(user, title, message, notif_type="", data=None):
    if not user:
        return None
    return Notification.objects.create(
        recipient=user,
        is_admin=False,
        title=title,
        message=message,
        notif_type=notif_type,
        data=data or {},
    )
