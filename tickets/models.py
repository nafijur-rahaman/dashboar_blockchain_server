from django.db import models
from django.conf import settings


class Ticket(models.Model):

    STATUS_CHOICES = (
        ("open", "Open"),
        ("pending", "Pending"),
        ("closed", "Closed"),
    )

    CATEGORY_CHOICES = (
        ("deposit_issue", "Deposit Issue"),
        ("withdraw_issue", "Withdraw Issue"),
        ("technical_issue", "Technical Issue"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets"
    )

    subject = models.CharField(max_length=255)

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.subject}"
    

class TicketMessage(models.Model):

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    message = models.TextField()

    attachment = models.FileField(
        upload_to="ticket_messages/",
        blank=True,
        null=True
    )

    is_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.email}"