from django.urls import path
from .views import *

urlpatterns = [

    path("deposit/request/", CreateDepositRequestAPI.as_view(), name="create-deposit-request"),
    path("deposit/get-my-deposits/", MyDepositRequestsAPI.as_view(), name="my-deposit-requests"),
    
    path("transactions/get-my-transaction-history/", TransactionHistoryAPI.as_view(), name="transaction-history"),
    path("transactions/get-my-balance/<int:coin_id>/", GetBalanceAPI.as_view(), name="get-balance"),
    
    path("admin/balance/update/", AdminBalanceUpdateAPI.as_view(), name="admin-balance-update"),
    path("admin/deposits/", AllDepositRequestsAPI.as_view(), name="all-deposit-requests"),
    path("admin/deposit/<int:pk>/action/", AdminDepositActionAPI.as_view(), name="admin-deposit-action"),
]