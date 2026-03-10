from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.shortcuts import get_object_or_404


from .models import Ticket, TicketMessage
from .serializers import TicketMessageSerializer, TicketSerializer, CreateTicketSerializer

from users.permissions import IsUser, IsAdmin, IsAdminOrUser
from notifications.utils import create_admin_notification, create_user_notification


class CreateTicketAPI(APIView):

    permission_classes = [IsUser]

    def post(self, request):

        serializer = CreateTicketSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():

            ticket = serializer.save()

            create_admin_notification(
                title="New support ticket",
                message=f"Ticket #{ticket.id} created: {ticket.subject}",
                notif_type="ticket_created",
                data={"ticket_id": ticket.id},
            )
            create_user_notification(
                user=request.user,
                title="Ticket created",
                message=f"Your ticket #{ticket.id} was created successfully.",
                notif_type="ticket_created",
                data={"ticket_id": ticket.id},
            )

            return Response({
                "message": "Ticket created successfully",
                "ticket_id": ticket.id
            })

        return Response(serializer.errors, status=400)



class AdminGetAllTickets(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):

        tickets = Ticket.objects.all().order_by("-created_at")

        serializer = TicketSerializer(tickets, many=True)

        return Response(serializer.data)


class MyTicketsAPI(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        tickets = Ticket.objects.filter(user=request.user)

        serializer = TicketSerializer(tickets, many=True)

        return Response(serializer.data)
    

class TicketDetailAPI(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):

        ticket = Ticket.objects.get(id=ticket_id)

        messages = ticket.messages.all().order_by("created_at")

        serializer = TicketMessageSerializer(messages, many=True)

        return Response({
            "ticket": TicketSerializer(ticket).data,
            "messages": serializer.data
        })
        



class ReplyTicketAPI(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):

        ticket = get_object_or_404(Ticket, id=ticket_id)

        if ticket.status == "closed":
            return Response({"error": "Ticket already closed"}, status=400)

        message = request.data.get("message")
        attachment = request.FILES.get("attachment")
        status_value = request.data.get("status")  

        if not message:
            return Response({"error": "Message required"}, status=400)

        is_admin = request.user.role == "admin"

        # create message
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            message=message,
            attachment=attachment,
            is_admin=is_admin
        )

        # status logic
        if is_admin:
            if status_value == "closed":
                ticket.status = "closed"
            else:
                ticket.status = "pending"
        else:
            ticket.status = "open"

        ticket.save()

        if is_admin:
            if status_value == "closed":
                create_user_notification(
                    user=ticket.user,
                    title="Ticket closed",
                    message=f"Your ticket #{ticket.id} was closed by admin.",
                    notif_type="ticket_closed",
                    data={"ticket_id": ticket.id},
                )
            else:
                create_user_notification(
                    user=ticket.user,
                    title="Admin replied",
                    message=f"Admin replied to your ticket #{ticket.id}.",
                    notif_type="ticket_reply",
                    data={"ticket_id": ticket.id},
                )
        else:
            create_admin_notification(
                title="New ticket reply",
                message=f"User replied to ticket #{ticket.id}.",
                notif_type="ticket_reply",
                data={"ticket_id": ticket.id},
            )

        return Response({"message": "Reply sent successfully"})
    
    
        
class CloseTicketAPI(APIView):

    permission_classes = [IsAdmin]

    def patch(self, request, ticket_id):

        ticket = get_object_or_404(Ticket, id=ticket_id)

        if request.user.role != "admin":
            return Response({"error": "Permission denied"}, status=403)

        last_admin_message = ticket.messages.filter(is_admin=True).last()

        if not last_admin_message:
            return Response(
                {"error": "Admin must reply before closing ticket"},
                status=400
            )

        ticket.status = "closed"
        ticket.save()

        create_user_notification(
            user=ticket.user,
            title="Ticket closed",
            message=f"Your ticket #{ticket.id} was closed by admin.",
            notif_type="ticket_closed",
            data={"ticket_id": ticket.id},
        )

        return Response({
            "message": "Ticket closed"
        })
        

