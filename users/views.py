from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

import logging
from smtplib import SMTPException
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.db import IntegrityError


from .serializers import (
    UserSerializer,
    AdminUserSerializer,
    RegisterSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ForgotPasswordRequestSerializer,
    ResetPasswordSerializer,
    AdminUserDetailSerializer
)
from .models import User
from .permissions import IsAdmin, IsUser, IsAdminOrUser
from django.utils import timezone
from wallet.services.pricing import get_coin_prices

logger = logging.getLogger(__name__)


class UserListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

class UserListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.filter(role="user").prefetch_related("balances__coin")

        status_filter = request.query_params.get("status")
        if status_filter in {"active", "inactive", "blocked"}:
            users = users.filter(status=status_filter)


        users = users.order_by("-id")

        paginator = UserListPagination()
        page = paginator.paginate_queryset(users, request, view=self)

        symbols = set()
        for user in page:
            for balance in user.balances.all():
                symbols.add((getattr(balance.coin, "symbol", "") or "").upper())
        price_map = get_coin_prices(symbols) if symbols else {}

        serializer = AdminUserSerializer(
            page,
            many=True,
            context={"request": request, "price_map": price_map},
        )
        return paginator.get_paginated_response(serializer.data)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, user_id):
        try:
            user = User.objects.prefetch_related(
                "transactions",
                "balances__coin"
            ).get(id=user_id, role="user")

        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        symbols = {
            (getattr(balance.coin, "symbol", "") or "").upper()
            for balance in user.balances.all()
        }
        price_map = get_coin_prices(symbols) if symbols else {}

        serializer = AdminUserDetailSerializer(
            user,
            context={"request": request, "_coin_usd_rates": price_map},
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


class BlockUserView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role="user")
            user.status = "blocked"
            user.is_active = False
            user.save(update_fields=["status", "is_active"])
            return Response({"message": "User blocked successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class UnblockUserView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role="user")
            user.status = "active"
            user.is_active = True
            user.save(update_fields=["status", "is_active"])
            return Response({"message": "User unblocked successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

# user register view
class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        try:
            if serializer.is_valid():
                user = serializer.save()
                return Response(
                    {
                        "email": user.email,
                        "fullname": user.full_name if user.full_name else "",
                        "role": user.role if user.role else "user",
                        "message": "User registered successfully"
                    },
                    status=status.HTTP_201_CREATED
                )

            # If serializer validation fails
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError as e:
            return Response(
                {"errors": {"email": ["Email already exists."]}},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
 
            return Response(
                {"errors": {"non_field_error": [str(e)]}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
# user login view
class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # update last login
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            token, _ = Token.objects.get_or_create(user=user)

            profile_pic_url = (
                request.build_absolute_uri(user.profile_pic.url)
                if user.profile_pic else ""
            )

            return Response({
                "token": token.key,
                "role": user.role,
                "fullname": user.full_name if user.full_name else "",
                "profile_pic": profile_pic_url,
                "message": "User logged in successfully"
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# password change view

class PasswordChangeView(APIView):
    permission_classes = [IsAdminOrUser]

    def post(self, request):
        # Pass the request in context so the serializer can access request.user
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordRequestView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"message": "Email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        frontend_base_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        reset_link = f"{frontend_base_url}/forgot-password?uid={uid}&token={token}"

        try:
            sent_count = send_mail(
                subject="Reset your password",
                message=f"Use this link to reset your password: {reset_link}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
                recipient_list=[email],
                fail_silently=False,
            )

            if sent_count == 0:
                logger.warning("Reset email was not sent to %s (send_mail returned 0).", email)
        except SMTPException:
            logger.exception("SMTP error while sending reset email to %s", email)
        except Exception:
            logger.exception("Unexpected error while sending reset email to %s", email)

        return Response(
            {"message": "Reset link sent to your email."},
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            request.user.auth_token.delete()
            return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user, context={"request": request})
        data = serializer.data
        data["fullname"] = user.full_name if user.full_name else ""
        data["profile_pic"] = request.build_absolute_uri(user.profile_pic.url) if user.profile_pic else ""
        return Response(data, status=status.HTTP_200_OK)
