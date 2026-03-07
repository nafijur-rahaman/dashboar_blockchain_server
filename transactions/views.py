from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from decimal import Decimal
from django.db import transaction

from wallet.models import WalletAssignment
from .models import DepositRequest, WalletBalance, Transaction
from .serializers import DepositRequestSerializer, WalletBalanceSerializer, TransactionSerializer,AdminGetDepositSerializer

from users.permissions import IsAdmin, IsUser, IsAdminOrUser



#------------------ Admin: Update Wallet Balance ------------------#

class AdminBalanceUpdateAPI(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request):

        user_id = request.data.get("user")
        coin_id = request.data.get("coin")
        amount = Decimal(request.data.get("amount", "0"))
        tx_type = request.data.get("type")

        balance, created = WalletBalance.objects.select_for_update().get_or_create(
            user_id=user_id,
            coin_id=coin_id
        )

        if tx_type == "admin_add":
            balance.balance += amount

        elif tx_type == "admin_deduct":
            if balance.balance < amount:
                return Response({"error": "Insufficient balance"}, status=400)

            balance.balance -= amount

        balance.save()

        Transaction.objects.create(
            user_id=user_id,
            coin_id=coin_id,
            amount=amount,
            transaction_type=tx_type
        )

        return Response({
            "message": "Balance updated",
            "new_balance": balance.balance
        })
    

# ------------------ Get Wallet Balance ------------------#

class GetBalanceAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request, coin_id):

        try:
            balance = WalletBalance.objects.select_related('coin').get(user=request.user, coin_id=coin_id)

            serializer = WalletBalanceSerializer(balance)

            return Response({
                "message": "Balance retrieved",
                "data": serializer.data
            })

        except WalletBalance.DoesNotExist:
            return Response({
                "error": "No balance found for this coin"
            }, status=404)
            
# ------------------ Get Transaction History ------------------#

class TransactionHistoryAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request):

        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

        serializer = TransactionSerializer(transactions, many=True)

        return Response({
            "message": "Transaction history retrieved",
            "data": serializer.data
        })


#------------------ Create deposit request ------------------#

class CreateDepositRequestAPI(APIView):
    permission_classes = [IsUser]

    @transaction.atomic
    def post(self, request):

        serializer = DepositRequestSerializer(data=request.data)

        if serializer.is_valid():
            deposit = serializer.save(user=request.user)

            Transaction.objects.create(
                user=request.user,
                coin=deposit.coin,
                amount=deposit.amount,
                transaction_type="deposit",
                status="pending",  
                reference=f"Deposit request ID {deposit.id}"
            )

            return Response({
                "message": "Deposit request submitted",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

#----------------- Get My deposits ------------------#

class MyDepositRequestsAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request):

        deposits = DepositRequest.objects.filter(user=request.user).order_by('-created_at')

        serializer = DepositRequestSerializer(deposits, many=True)

        return Response({
            "message": "My deposit requests retrieved",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
        

#----------------- Admin: Get all deposits ------------------#

class AllDepositRequestsAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):

        deposits = DepositRequest.objects.select_related(
            "user", "coin", "network"
        ).order_by("-created_at")

        user_ids = set(d.user_id for d in deposits)
        coin_ids = set(d.coin_id for d in deposits)

        # PRE-COMPUTE balances
        balances = WalletBalance.objects.filter(
            user_id__in=user_ids,
            coin_id__in=coin_ids
        ).values('user_id', 'coin_id', 'balance')
        balance_map = {(b['user_id'], b['coin_id']): b['balance'] for b in balances}

        # PRE-COMPUTE wallet addresses
        wallet_addresses = WalletAssignment.objects.filter(
            user_id__in=user_ids,
            coin_id__in=coin_ids
        ).values('user_id', 'coin_id', 'wallet_address')
        wallet_map = {(w['user_id'], w['coin_id']): w['wallet_address'] for w in wallet_addresses}

        serializer = AdminGetDepositSerializer(
            deposits,
            many=True,
            context={
                "balance_map": balance_map,
                "wallet_map": wallet_map
            }
        )

        return Response({
            "message": "All deposit requests retrieved",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
        

# ----------------- Admin: Approve/Reject deposit ------------------#

class AdminDepositActionAPI(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request, pk):

        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response({"error": "Invalid action"}, status=400)

        try:
            deposit = DepositRequest.objects.select_for_update().get(pk=pk)

            # already processed check
            if deposit.status != "pending":
                return Response({"error": "Already processed"}, status=400)

            # negative or zero amount protection
            if deposit.amount <= 0:
                deposit.status = "failed"
                deposit.save(update_fields=["status"])

                Transaction.objects.filter(
                    reference=f"Deposit request ID {deposit.id}"
                ).update(status="failed")

                return Response({"error": "Invalid deposit amount"}, status=400)

            # ======================
            # APPROVE DEPOSIT
            # ======================
            if action == "approve":

                balance, _ = WalletBalance.objects.select_for_update().get_or_create(
                    user=deposit.user,
                    coin=deposit.coin
                )

                balance.balance += deposit.amount
                balance.save(update_fields=["balance"])

                # update existing pending transaction
                Transaction.objects.filter(
                    reference=f"Deposit request ID {deposit.id}"
                ).update(status="success")

                deposit.status = "approved"
                deposit.save(update_fields=["status"])

                return Response({"message": "Deposit approved"})


            # ======================
            # REJECT DEPOSIT
            # ======================
            elif action == "reject":

                deposit.status = "rejected"
                deposit.save(update_fields=["status"])

                Transaction.objects.filter(
                    reference=f"Deposit request ID {deposit.id}"
                ).update(status="failed")

                return Response({"message": "Deposit rejected"})


        except DepositRequest.DoesNotExist:
            return Response({"error": "Deposit not found"}, status=404)

        except Exception as e:

            # fallback safety
            deposit.status = "failed"
            deposit.save(update_fields=["status"])

            Transaction.objects.filter(
                reference=f"Deposit request ID {deposit.id}"
            ).update(status="failed")

            return Response(
                {"error": "Deposit processing failed", "details": str(e)},
                status=500
            )