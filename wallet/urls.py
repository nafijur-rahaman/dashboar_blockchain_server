from django.urls import path
from .views import AdminWalletListAPI, AdminWalletDetailAPI, CoinNetworkListAPI,MyWalletsAPI

urlpatterns = [
    path('coins-networks/', CoinNetworkListAPI.as_view(), name='coin-network-list'),
    path('admin/wallets/', AdminWalletListAPI.as_view(), name='admin-wallet-list'),
    path('admin/wallets/<int:pk>/', AdminWalletDetailAPI.as_view(), name='admin-wallet-detail'),
    path('my-wallets/', MyWalletsAPI.as_view(), name='my-wallets'),
]