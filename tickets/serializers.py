from rest_framework import serializers
from .models import Ticket, TicketMessage


class CreateTicketSerializer(serializers.ModelSerializer):

    message = serializers.CharField(write_only=True)

    class Meta:
        model = Ticket
        fields = [
            "subject",
            "category",
            "message"
        ]

    def create(self, validated_data):

        message = validated_data.pop("message")
        user = self.context["request"].user

        ticket = Ticket.objects.create(
            user=user,
            **validated_data
        )

        TicketMessage.objects.create(
            ticket=ticket,
            sender=user,
            message=message,
            is_admin=False
        )

        return ticket
    

class TicketSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ticket
        fields = "__all__"
        
class TicketMessageSerializer(serializers.ModelSerializer):

    sender = serializers.StringRelatedField()

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "sender",
            "message",
            "attachment",
            "is_admin",
            "created_at"
        ]