from django.contrib import admin
from .models import CoinPrice, CryptoCoin, CryptoNetwork, WalletAssignment

admin.site.register(CryptoCoin)
admin.site.register(CryptoNetwork)
admin.site.register(WalletAssignment)
admin.site.register(CoinPrice)

