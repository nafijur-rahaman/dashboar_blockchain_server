from django.urls import path
from .views import *

urlpatterns = [

    path("create/", CreateTicketAPI.as_view(), name="create-ticket"),

    path("my-tickets/", MyTicketsAPI.as_view(), name="my-tickets"),
    
    path("admin/all-tickets/", AdminGetAllTickets.as_view(), name="admin-all-tickets"),

    path("detail/<int:ticket_id>/", TicketDetailAPI.as_view(), name="ticket-detail"),

    path("reply/<int:ticket_id>/", ReplyTicketAPI.as_view(), name="reply-ticket"),

    path("close/<int:ticket_id>/", CloseTicketAPI.as_view(), name="close-ticket"),

]