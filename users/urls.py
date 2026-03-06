from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    PasswordChangeView,
    ForgotPasswordRequestView,
    ResetPasswordView,
    LogoutView,
    UserMeView,
)

urlpatterns = [
    path('user/register/', RegisterView.as_view(), name='register'),
    path('user/login/', LoginView.as_view(), name='login'),
    path('user/forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot_password'),
    path('user/reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('user/me/', UserMeView.as_view(), name='user_me'),
    path('logout', LogoutView.as_view(), name = "logout"),

    
    
    path('change-password/', PasswordChangeView.as_view(), name='change_password'),
]
