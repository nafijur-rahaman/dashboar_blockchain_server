from rest_framework import serializers
from .models import WalletBalance, Transaction, DepositRequest, WithdrawRequest

class WalletBalanceSerializer(serializers.ModelSerializer):
    coin_name = serializers.ReadOnlyField(source="coin.name")
    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    usd_value = serializers.SerializerMethodField()
    class Meta:
        model = WalletBalance
        fields = ['id', 'user', 'coin', 'coin_name', 'coin_symbol', 'balance', 'usd_value', 'updated_at']

    def get_usd_value(self, obj):
        rates = self.context.get("price_map") or self.context.get("_coin_usd_rates") or {}
        symbol = (getattr(obj.coin, "symbol", "") or "").upper()
        rate = rates.get(symbol)
        if not rate:
            return "0"
        try:
            return str(obj.balance * rate)
        except Exception:
            return "0"
        
class TransactionSerializer(serializers.ModelSerializer):
    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'coin', 'coin_symbol', 'amount', 'transaction_type','status', 'reference', 'created_at']
        
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
    user_status = serializers.ReadOnlyField(source="user.status")
    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    network_name = serializers.ReadOnlyField(source="network.network_name")
    amount_usd = serializers.SerializerMethodField()

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
            'user_status',
            'coin',
            'coin_symbol',
            'network',
            'network_name',
            'amount',
            'amount_usd',
            'tx_hash',
            'proof',
            'status',
            'created_at',
            'user_balance',
            'wallet_address',
        ]
        read_only_fields = ['status']

    def get_user_balance(self, obj):
        total_balance_map = self.context.get("total_balance_map", {})
        return total_balance_map.get(obj.user_id, 0)

    def get_wallet_address(self, obj):
        # precomputed wallet map
        wallet_map = self.context.get("wallet_map", {})
        return wallet_map.get((obj.user_id, obj.coin_id))
    
    def get_amount_usd(self, obj):
        price_map = self.context.get("price_map", {})
        symbol = (getattr(obj.coin, "symbol", "") or "").upper()
        rate = price_map.get(symbol)
        if not rate:
            return 0
        return obj.amount * rate
    
    

class WithdrawRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawRequest 
        fields = [
            "id",
            "coin",
            "network",
            "convert_amount",
            "wallet_address",
            "amount",
            "status",
            "created_at"
        ]

        read_only_fields = ["status", "created_at", "user", "convert_amount"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_wallet_address(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("Invalid wallet address")
        return value

    def validate(self, data):
        coin = data["coin"]
        network = data["network"]

        # ensure network belongs to coin
        if network.coin_id != coin.id:
            raise serializers.ValidationError("Invalid network for this coin")

        return data
    
class AdminWithdrawSerializer(serializers.ModelSerializer):

    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    network_name = serializers.ReadOnlyField(source="network.network_name")
    user_name = serializers.ReadOnlyField(source="user.full_name")
    user_email = serializers.ReadOnlyField(source="user.email")
    user_status = serializers.ReadOnlyField(source="user.status")
    user_balance = serializers.SerializerMethodField()

    class Meta:
        model = WithdrawRequest
        fields = [
            "id",
            "user",
            "user_name",
            "user_email",
            "user_status",
            "coin",
            "coin_symbol",
            "network",
            "network_name",
            "wallet_address",
            "amount",
            "convert_amount",
            "status",
            "created_at",
            "user_balance"
        ]

    def get_user_balance(self, obj):
        total_balance_map = self.context.get("total_balance_map", {})
        return total_balance_map.get(obj.user_id, 0)



class BalanceAdjustmentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    coin_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=8)
    action = serializers.ChoiceField(choices=["add", "subtract"])
    description = serializers.CharField(required=False)
    internal_note = serializers.CharField(required=False)
