from django.db import models
from django.conf import settings




class WalletBalance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='balances'
    )
    
    coin = models.ForeignKey(
        'wallet.CryptoCoin', on_delete=models.CASCADE, related_name='balances'
    )
    
    balance = models.DecimalField(
        max_digits=20, decimal_places=8, default=0
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'coin')
        indexes = [
        models.Index(fields=["user", "coin"]),
        ]
    def __str__(self):
        return f"{self.user.email} - {self.coin.symbol}: {self.balance}"
    



TRANSACTION_TYPE = (
        ('deposit', 'Deposit'), 
        ('withdraw', 'Withdraw'),
        ('admin_add', 'Admin Add'),
        ('admin_deduct', 'Admin Deduct'),
    )

STATUS = (
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed"),
)
class Transaction(models.Model):
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions'
    )
    
    coin = models.ForeignKey(
        'wallet.CryptoCoin', on_delete=models.CASCADE, related_name='transactions'
    )
    
    amount = models.DecimalField(
        max_digits=20, decimal_places=8, default=0
    )
    
    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPE
    )
    
    internal_note = models.TextField(
        blank=True,
        null=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS, default="success")
    
    reference = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.coin.symbol}: {self.amount}"
    
    class Meta:
        indexes = [
        models.Index(fields=["user"]),
        models.Index(fields=["coin"]),
        models.Index(fields=["transaction_type"]),
        ]
    
    
    
    
    
STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )    

class DepositRequest(models.Model):
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposit_requests'
    )
    
    coin = models.ForeignKey(
        'wallet.CryptoCoin', on_delete=models.CASCADE, related_name='deposit_requests' 
    )
    
    network = models.ForeignKey(
        'wallet.CryptoNetwork', on_delete=models.CASCADE, related_name='deposit_requests'
    )
    
    amount = models.DecimalField(
        max_digits=20, decimal_places=8, default=0
    )
    
    tx_hash = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    
    proof = models.ImageField(
        upload_to='deposit_proofs/', blank=True, null=True
    )
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.coin.symbol}: {self.amount} ({self.status})"


class WithdrawRequest(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdraw_requests"
    )

    coin = models.ForeignKey(
        "wallet.CryptoCoin",
        on_delete=models.PROTECT
    )

    network = models.ForeignKey(
        "wallet.CryptoNetwork",
        on_delete=models.PROTECT
    )
 
    wallet_address = models.CharField(max_length=255)

    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8
    )
    convert_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.coin.symbol} - {self.amount}"