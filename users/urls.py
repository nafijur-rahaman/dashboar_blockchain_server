from django.urls import path
from .views import RegisterView, LoginView, PasswordChangeView

urlpatterns = [
    path('user/register/', RegisterView.as_view(), name='register'),
    path('user/login/', LoginView.as_view(), name='login'),

    
    
    path('change-password/', PasswordChangeView.as_view(), name='change_password'),
]