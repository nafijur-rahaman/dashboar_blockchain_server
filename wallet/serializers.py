from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import serializers
from .models import CryptoCoin, CryptoNetwork, WalletAssignment


SYMBOL_ALIASES = {
    "USD": "USDT",
}


def _normalize_symbol(value: str) -> str:
    return (value or "").upper().strip().replace(" ", "").replace("-", "").replace("/", "_")


class CryptoNetworkSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CryptoNetwork
        fields = ['id', 'network_name']
        
class CryptoCoinSerializer(serializers.ModelSerializer):
    networks = CryptoNetworkSerializer(many=True, required=False)

    class Meta:
        model = CryptoCoin
        fields = ['id', 'name', 'symbol', 'is_active', 'networks']

    def validate_symbol(self, value):
        normalized = _normalize_symbol(value)
        if not normalized:
            raise serializers.ValidationError("Symbol is required.")
        return SYMBOL_ALIASES.get(normalized, normalized)

    def create(self, validated_data):
        networks_data = validated_data.pop('networks', [])
        coin = CryptoCoin.objects.create(**validated_data)

        for network_name in self._prepare_network_names(networks_data):
            CryptoNetwork.objects.create(coin=coin, network_name=network_name)

        return coin

    def _prepare_network_names(self, networks_data):
        network_names = []
        seen_names = set()

        for network in networks_data:
            network_name = (network.get('network_name') or '').strip()
            if not network_name:
                continue

            normalized_name = network_name.casefold()
            if normalized_name in seen_names:
                continue

            seen_names.add(normalized_name)
            network_names.append(network_name)

        return network_names

    @transaction.atomic
    def update(self, instance, validated_data):
        networks_data = validated_data.pop('networks', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if networks_data is not None:
            existing_networks = {
                network.id: network for network in instance.networks.all()
            }
            retained_network_ids = set()
            seen_names = set()

            for network in networks_data:
                network_id = network.get('id')
                network_name = (network.get('network_name') or '').strip()

                if not network_name:
                    continue

                normalized_name = network_name.casefold()
                if normalized_name in seen_names:
                    continue
                seen_names.add(normalized_name)

                if network_id is not None:
                    existing_network = existing_networks.get(network_id)
                    if existing_network is None:
                        raise serializers.ValidationError(
                            {"networks": f"Network id {network_id} does not belong to this coin."}
                        )

                    if existing_network.network_name != network_name:
                        existing_network.network_name = network_name
                        existing_network.save(update_fields=["network_name"])

                    retained_network_ids.add(existing_network.id)
                    continue

                new_network = CryptoNetwork.objects.create(
                    coin=instance,
                    network_name=network_name,
                )
                retained_network_ids.add(new_network.id)

            removable_networks = instance.networks.exclude(id__in=retained_network_ids)
            try:
                removable_networks.delete()
            except ProtectedError:
                raise serializers.ValidationError(
                    {
                        "networks": (
                            "One or more networks are already assigned to wallets. "
                            "Reassign or deactivate those wallets before removing the network."
                        )
                    }
                )

        return instance

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
            'is_active',
            'created_at',
        ]

    def validate(self, data):
        instance = getattr(self, 'instance', None)

        coin = data.get('coin') or getattr(instance, 'coin', None)
        network = data.get('network') or getattr(instance, 'network', None)
        user = data.get('user') or getattr(instance, 'user', None)
        wallet_address = data.get('wallet_address') or getattr(instance, 'wallet_address', '')
        is_active = data.get('is_active')
        if is_active is None:
            is_active = getattr(instance, 'is_active', True)

        if not coin or not network:
            raise serializers.ValidationError("Coin and network are required.")

        if network.coin != coin:
            raise serializers.ValidationError(
                "Selected network does not belong to this coin."
            )

        # Only enforce duplicate checks for active assignments.
        if is_active:
            qs = WalletAssignment.objects.filter(
                coin=coin,
                network=network,
                is_active=True,
            )
            if instance:
                qs = qs.exclude(pk=instance.pk)

            if user and qs.filter(user=user).exists():
                raise serializers.ValidationError(
                    "This user already has an active wallet for the selected coin/network."
                )

            if wallet_address and qs.filter(wallet_address=wallet_address).exists():
                raise serializers.ValidationError(
                    "This wallet address is already assigned for the selected coin/network."
                )

        return data
