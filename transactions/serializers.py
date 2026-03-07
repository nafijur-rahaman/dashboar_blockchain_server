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
    
class AdminGetDepositSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source="user.full_name")
    user_email = serializers.ReadOnlyField(source="user.email")
    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    network_name = serializers.ReadOnlyField(source="network.network_name")

    # balance for this deposit's coin
    user_balance = serializers.SerializerMethodField()
    # wallet address for this deposit's coin
    wallet_address = serializers.SerializerMethodField()

    class Meta:
        model = DepositRequest
        fields = [
            'id',
            'user',
            'user_name',
            'user_email',
            'coin',
            'coin_symbol',
            'network',
            'network_name',
            'amount',
            'tx_hash',
            'proof',
            'status',
            'created_at',
            'user_balance',
            'wallet_address',
        ]
        read_only_fields = ['status']

    def get_user_balance(self, obj):
        balance_map = self.context.get("balance_map", {})
        return balance_map.get((obj.user_id, obj.coin_id), 0)

    def get_wallet_address(self, obj):
        # precomputed wallet map
        wallet_map = self.context.get("wallet_map", {})
        return wallet_map.get((obj.user_id, obj.coin_id))