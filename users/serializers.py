from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from decimal import Decimal, ROUND_DOWN

from transactions.models import Transaction
from transactions.serializers import TransactionSerializer, WalletBalanceSerializer, WalletBalanceSerializer
from .models import User
from wallet.services.pricing import get_coin_prices


# user serializer

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'phone', 'address', 'profile_pic', 'role']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'phone', 'address', 'profile_pic']


class AdminUserSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "balance", "status"]

    def get_balance(self, obj):
        balances = obj.balances.select_related("coin").all()
        rates = self.context.get("price_map", {})

        total_usdt = Decimal("0")
        for balance in balances:
            symbol = (getattr(balance.coin, "symbol", "") or "").upper()
            rate = rates.get(symbol)
            if not rate:
                continue
            total_usdt += Decimal(str(balance.balance)) * rate

        return total_usdt.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

class AdminTransactionSerializer(serializers.ModelSerializer):
    coin_symbol = serializers.ReadOnlyField(source="coin.symbol")
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'coin', 'coin_symbol', 'amount', 'transaction_type','status', 'reference','internal_note', 'created_at']

class AdminUserDetailSerializer(serializers.ModelSerializer):
    transactions = serializers.SerializerMethodField()
    wallet_balances = WalletBalanceSerializer(many=True, read_only=True, source="balances")
    total_balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", 'profile_pic', "address", "email", "total_balance", "status", "transactions", "wallet_balances","last_login"]
        
    def get_total_balance(self, obj):
        balances = obj.balances.select_related("coin").all()
        rates = self._get_coin_usd_rates(balances)

        total_usdt = Decimal("0")
        for balance in balances:
            symbol = (getattr(balance.coin, "symbol", "") or "").upper()
            rate = rates.get(symbol)
            if not rate:
                continue
            total_usdt += Decimal(str(balance.balance)) * rate

        return total_usdt.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

    def get_transactions(self, obj):
        queryset = obj.transactions.select_related("coin").order_by("-created_at")
        return AdminTransactionSerializer(queryset, many=True).data

    def _get_coin_usd_rates(self, balances):
        # Cache rates in serializer context for reuse inside the same request lifecycle.
        cache = self.context.setdefault("_coin_usd_rates", {})

        symbols = {
            (getattr(balance.coin, "symbol", "") or "").upper()
            for balance in balances
        }

        missing_symbols = [symbol for symbol in symbols if symbol not in cache]
        if not missing_symbols:
            return cache

        rates = get_coin_prices(missing_symbols)
        cache.update(rates)

        return cache


# user register serializer

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "full_name",
            "phone",
            "address",
            "profile_pic",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user



# user login serializer

class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        user = authenticate(
            username=data["email"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        data["user"] = user
        return data
    

# password change serializer
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})

        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except Exception:
            raise serializers.ValidationError({"uid": ["Invalid reset link."]})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": ["Invalid or expired reset link."]})

        validate_password(attrs["new_password"], user=user)

        attrs["user"] = user
        return attrs



