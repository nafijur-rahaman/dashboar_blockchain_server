from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    is_admin = models.BooleanField(default=False)
    title = models.CharField(max_length=120)
    message = models.TextField()
    notif_type = models.CharField(max_length=50, blank=True)
    data = models.JSONField(blank=True, null=True, default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
