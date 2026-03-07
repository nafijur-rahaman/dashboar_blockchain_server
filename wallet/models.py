from django.db import models
from django.conf import settings



class CryptoCoin(models.Model):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=10, unique=True) # BTC, USDT
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class CryptoNetwork(models.Model):
    coin = models.ForeignKey(CryptoCoin, on_delete=models.CASCADE, related_name='networks')
    network_name = models.CharField(max_length=50) # TRC20, BEP20

    def __str__(self):
        return f"{self.coin.symbol} - {self.network_name}"


class WalletAssignment(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='assigned_wallets')

    coin = models.ForeignKey(CryptoCoin,
                             on_delete=models.PROTECT,
                             related_name='assigned_wallets')

    network = models.ForeignKey(CryptoNetwork,
                                on_delete=models.PROTECT,
                                related_name='assigned_wallets')

    wallet_address = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'coin', 'network']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.coin.symbol} ({self.network.network_name})"