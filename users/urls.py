from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    PasswordChangeView,
    ForgotPasswordRequestView,
    ResetPasswordView,
    LogoutView,
    UserListView,
    UserMeView,
    BlockUserView,
    UnblockUserView,
    UserDetailView,
)

urlpatterns = [
    path('user/register/', RegisterView.as_view(), name='register'),
    path('user/login/', LoginView.as_view(), name='login'),
    path('user/forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot_password'),
    path('user/reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('user/me/', UserMeView.as_view(), name='user_me'),
    path('logout', LogoutView.as_view(), name = "logout"),

    
    
    path('change-password/', PasswordChangeView.as_view(), name='change_password'),
    path('get-all-users/', UserListView.as_view(), name='get_all_users'),
    path("users/<int:user_id>/", UserDetailView.as_view(), name="user_detail"),
    path("block-user/<int:user_id>/",BlockUserView.as_view(), name="block_user"), 
    path("unblock-user/<int:user_id>/", UnblockUserView.as_view(), name="unblock_user"),
]
