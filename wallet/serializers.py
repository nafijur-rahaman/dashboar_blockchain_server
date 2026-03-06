from rest_framework import serializers
from .models import CryptoCoin, CryptoNetwork, WalletAssignment


class CryptoNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CryptoNetwork
        fields = ['id', 'network_name']
        
class CryptoCoinSerializer(serializers.ModelSerializer):
    networks = CryptoNetworkSerializer(many=True, read_only=True)

    class Meta:
        model = CryptoCoin
        fields = ['id', 'name', 'symbol', 'is_active', 'networks']

class WalletAssignmentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source='user.full_name')
    coin_symbol = serializers.ReadOnlyField(source='coin.symbol')
    network_name = serializers.ReadOnlyField(source='network.network_name')

    class Meta:
        model = WalletAssignment
        fields = [
            'id',
            'user',
            'full_name',
            'coin',
            'coin_symbol',
            'network',
            'network_name',
            'wallet_address',
            'is_active'
        ]

    def validate(self, data):
        coin = data.get('coin')
        network = data.get('network')

        if network.coin != coin:
            raise serializers.ValidationError(
                "Selected network does not belong to this coin."
            )

        return data