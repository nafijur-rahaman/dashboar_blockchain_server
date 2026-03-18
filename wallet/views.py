from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db import IntegrityError
from users.permissions import IsAdmin, IsUser




from .models import CryptoCoin, CryptoNetwork, WalletAssignment
from .serializers import CryptoCoinSerializer, CryptoNetworkSerializer, WalletAssignmentSerializer



class CoinNetworkListAPI(APIView):
    permission_classes = [IsAdmin]
    def get(self, request):
        coins = CryptoCoin.objects.filter(is_active=True)
        serializer = CryptoCoinSerializer(coins, many=True)
        return Response(serializer.data)


class AdminCoinListAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        coins = CryptoCoin.objects.all().order_by('name')
        serializer = CryptoCoinSerializer(coins, many=True)
        return Response(serializer.data)


class CryptoCoinView(APIView):
    permission_classes = [IsAdmin]
    
    def post(self, request):
        serializer = CryptoCoinSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
            except ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        try:
            coin = CryptoCoin.objects.get(pk=pk)
            serializer = CryptoCoinSerializer(coin, data=request.data, partial=True)
            if serializer.is_valid():
                try:
                    serializer.save()
                except ValidationError as exc:
                    return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except CryptoCoin.DoesNotExist:
            return Response({"error": "Coin not found"}, status=status.HTTP_404_NOT_FOUND)
        
    def delete(self, request, pk):
        try:
            coin = CryptoCoin.objects.get(pk=pk)
            coin.is_active = False
            coin.save()
            return Response({"message": "Coin deactivated"}, status=status.HTTP_200_OK)
        except CryptoCoin.DoesNotExist:
            return Response({"error": "Coin not found"}, status=status.HTTP_404_NOT_FOUND)

class AdminWalletControlAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        assignments = WalletAssignment.objects.select_related(
            'user',
            'coin',
            'network',
        ).order_by('-created_at')
        serializer = WalletAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        user_id = data.get('user')
        coin_id = data.get('coin')
        network_id = data.get('network')

        if user_id and coin_id and network_id:
            existing_inactive = WalletAssignment.objects.filter(
                user_id=user_id,
                coin_id=coin_id,
                network_id=network_id,
                is_active=False,
            ).first()

            if existing_inactive:
                serializer = WalletAssignmentSerializer(
                    existing_inactive,
                    data=data,
                    partial=True,
                )
                if serializer.is_valid():
                    serializer.save(is_active=True)
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = WalletAssignmentSerializer(data=data)
        if serializer.is_valid():
            try:
                serializer.save()
            except IntegrityError:
                return Response(
                    {"error": "Duplicate wallet assignment is not allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AdminWalletDetailAPI(APIView):
    permission_classes = [IsAdmin]


    def get(self, request, pk):
        try:
            assignment = WalletAssignment.objects.get(pk=pk)
            serializer = WalletAssignmentSerializer(assignment)
            return Response(serializer.data)
        except WalletAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    #  Edit/Reassign
    def patch(self, request, pk):
        try:
            assignment = WalletAssignment.objects.get(pk=pk)

            serializer = WalletAssignmentSerializer(assignment, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Wallet reassigned/updated successfully!",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except WalletAssignment.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

    #  Delete 
    def delete(self, request, pk):
        try:
            assignment = WalletAssignment.objects.get(pk=pk)
            assignment.is_active = False
            assignment.save()
            return Response({"message": "Wallet removed from user"}, status=status.HTTP_200_OK)
        except WalletAssignment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        

class MyWalletsAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request):
        wallets = WalletAssignment.objects.filter(
            user=request.user,
            is_active=True
        )

        serializer = WalletAssignmentSerializer(wallets, many=True)
        return Response(serializer.data)
