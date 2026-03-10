from django.urls import path
from .views import *

urlpatterns = [

    path("deposit/request/", CreateDepositRequestAPI.as_view(), name="create-deposit-request"),
    path("deposit/get-my-deposits/", MyDepositRequestsAPI.as_view(), name="my-deposit-requests"),
    path("admin/all-deposits/", AllDepositRequestsAPI.as_view(), name="all-deposit-requests"),
    
    path("withdraw/request/", CreateWithdrawRequestAPI.as_view(), name="create-withdraw-request"),
    path("withdraw/get-my-withdraws/", MyWithdrawRequestsAPI.as_view(), name="my-withdraw-requests"),
    path("admin/all-withdraws/", AdminWithdrawListAPI.as_view(), name="admin-all-withdraws"),


    
    path("transactions/get-my-transaction-history/", TransactionHistoryAPI.as_view(), name="transaction-history"),
    path("transactions/get-my-balance/<int:coin_id>/", GetBalanceAPI.as_view(), name="get-balance"),
    
    path("admin/balance-adjust/", AdminBalanceAdjustmentAPI.as_view(), name="admin-balance-adjust"),
    
 
    path("admin/deposit/<int:pk>/action/", AdminDepositActionAPI.as_view(), name="admin-deposit-action"),
    
    path("admin/withdraw/<int:pk>/action/", AdminWithdrawActionAPI.as_view(), name="admin-withdraw-action"),
    path("admin/dashboard-stats/", AdminDashboardStatsAPI.as_view(), name="admin-dashboard-stats"),
    path("admin/transactions/<int:pk>/", AdminTransactionDetailAPI.as_view(), name="admin-transaction-detail"),
    path("admin/withdraws/<int:pk>/", AdminWithdrawDetailAPI.as_view(), name="admin-withdraw-detail"),
]
