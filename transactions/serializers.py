from rest_framework import serializers
from .models import WalletBalance, Transaction, DepositRequest

class WalletBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletBalance
        fields = ['id', 'user', 'coin', 'balance', 'updated_at']
        
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'coin', 'amount', 'transaction_type','status', 'reference', 'created_at']
        
class DepositRequestSerializer(serializers.ModelSerializer):

    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    network_name = serializers.ReadOnlyField(source="network.network_name")

    class Meta:
        model = DepositRequest
        fields = [
            'id',
            'coin',
            'network',
            'amount',
            'tx_hash',
            'proof',
            'status',
            'created_at',
            'coin_symbol',
            'network_name'
        ]
        read_only_fields = ['status']
    