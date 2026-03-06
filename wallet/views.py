from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from users.permissions import IsAdmin, IsUser




from .models import CryptoCoin, CryptoNetwork, WalletAssignment
from .serializers import CryptoCoinSerializer, CryptoNetworkSerializer, WalletAssignmentSerializer



class CoinNetworkListAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        coins = CryptoCoin.objects.filter(is_active=True)
        serializer = CryptoCoinSerializer(coins, many=True)
        return Response(serializer.data)


class AdminWalletControlAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        assignments = WalletAssignment.objects.filter(is_active=True).order_by('-created_at')
        serializer = WalletAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WalletAssignmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AdminWalletDetailAPI(APIView):
    permission_classes = [IsAdminUser]


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