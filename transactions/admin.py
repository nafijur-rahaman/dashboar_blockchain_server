from django.contrib import admin
from .models import WalletBalance, Transaction, DepositRequest

admin.site.register(WalletBalance)
admin.site.register(Transaction)
admin.site.register(DepositRequest)

