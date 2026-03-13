from django.urls import path
from .views import AdminCoinListAPI, AdminWalletControlAPI, AdminWalletDetailAPI, CoinNetworkListAPI, CryptoCoinView,MyWalletsAPI

urlpatterns = [
    path('admin/all-coins/', CoinNetworkListAPI.as_view(), name='coin-list'),
    path('admin/coins/', AdminCoinListAPI.as_view(), name='admin-coin-list'),
    path("admin/create-coin/", CryptoCoinView.as_view(), name="create-coin"),
    path('admin/update-coin/<int:pk>/', CryptoCoinView.as_view(), name='update-coin'),
    path('admin/delete-coin/<int:pk>/', CryptoCoinView.as_view(), name='delete-coin'),
    
    
    path('admin/wallets/', AdminWalletControlAPI.as_view(), name='admin-wallet-list'),
    path('admin/wallets/<int:pk>/', AdminWalletDetailAPI.as_view(), name='admin-wallet-detail'),
    
    
    path('user/my-wallets/', MyWalletsAPI.as_view(), name='my-wallets'),
]
