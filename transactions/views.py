from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from decimal import Decimal, ROUND_DOWN
from django.db import transaction

from wallet.models import CryptoCoin, WalletAssignment
from wallet.services.pricing import get_coin_prices
from wallet.services.pricing import get_coin_price
from .models import DepositRequest, WalletBalance, Transaction, WithdrawRequest
from .serializers import BalanceAdjustmentSerializer, DepositRequestSerializer, WalletBalanceSerializer, TransactionSerializer, AdminGetDepositSerializer, WithdrawRequestSerializer, AdminWithdrawSerializer

from users.permissions import IsAdmin, IsUser, IsAdminOrUser
from notifications.utils import create_admin_notification, create_user_notification

# ------------------ Admin: Update Wallet Balance ------------------#

class AdminBalanceAdjustmentAPI(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request):

        try:

            serializer = BalanceAdjustmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            user_id = data["user_id"]
            coin_id = data["coin_id"]
            amount = data["amount"]
            action = data["action"]
            ref = data.get(
                "description", f"Admin balance {action} of {amount} for user {user_id} and coin {coin_id}")
            internal_note = data.get("internal_note", "")
            try:
                coin = CryptoCoin.objects.get(id=coin_id)
                # Lock wallet row to prevent race conditions
                balance, _ = WalletBalance.objects.select_for_update().get_or_create(
                    user_id=user_id,
                    coin=coin,
                    defaults={"balance": 0}
                )
                # Adjust balance atomically
                if action == "add":
                    balance.balance += amount
                    tx_type = "admin_add"
                else:  # subtract
                    if balance.balance < amount:
                        return Response({"error": "Insufficient balance"}, status=400)
                    balance.balance -= amount
                    tx_type = "admin_deduct"
                balance.save(update_fields=["balance"])
                # Record transaction
                created_tx = Transaction.objects.create(
                    user_id=user_id,
                    coin=coin,
                    amount=amount,
                    transaction_type=tx_type,
                    status="success",
                    reference=ref,
                    internal_note=internal_note,
                )
                return Response(
                    {
                        "message": "Balance adjusted successfully",
                        "new_balance": balance.balance,
                        "transaction": {
                            "id": created_tx.id,
                            "coin": coin.id,
                            "coin_symbol": coin.symbol,
                            "amount": str(created_tx.amount),
                            "transaction_type": created_tx.transaction_type,
                            "status": created_tx.status,
                            "reference": created_tx.reference,
                            "internal_note": created_tx.internal_note,
                            "created_at": created_tx.created_at,
                        },
                    },
                    status=status.HTTP_200_OK
                )
            except CryptoCoin.DoesNotExist:
                    return Response({"error": "Coin not found"}, status=404)
        except Exception as e:
            return Response({"error": "Balance adjustment failed", "details": str(e)}, status=500)

# ------------------ Get Wallet Balance ------------------#


class GetBalanceAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request, coin_id):

        try:
            balance = WalletBalance.objects.select_related(
                'coin').get(user=request.user, coin_id=coin_id)

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

        transactions = Transaction.objects.filter(
            user=request.user).order_by('-created_at')

        serializer = TransactionSerializer(transactions, many=True)

        return Response({
            "message": "Transaction history retrieved",
            "data": serializer.data
        })


# ------------------ Create deposit request ------------------#

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

            create_admin_notification(
                title="New deposit request",
                message=f"User {request.user.email} requested deposit #{deposit.id}.",
                notif_type="deposit_requested",
                data={"deposit_id": deposit.id},
            )
            create_user_notification(
                user=request.user,
                title="Deposit request submitted",
                message=f"Your deposit request #{deposit.id} was submitted.",
                notif_type="deposit_requested",
                data={"deposit_id": deposit.id},
            )

            return Response({
                "message": "Deposit request submitted",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------- Get My deposits ------------------#

class MyDepositRequestsAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request):

        deposits = DepositRequest.objects.filter(
            user=request.user).order_by('-created_at')

        serializer = DepositRequestSerializer(deposits, many=True)

        return Response({
            "message": "My deposit requests retrieved",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


# ----------------- Admin: Get all deposits ------------------#

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
            user_id__in=user_ids
        ).select_related("coin")
        balance_map = {
            (b.user_id, b.coin_id): b.balance
            for b in balances
        }

        symbols = {
            (getattr(b.coin, "symbol", "") or "").upper()
            for b in balances
        }
        price_map = get_coin_prices(symbols) if symbols else {}

        total_balance_map = {}
        for b in balances:
            symbol = (getattr(b.coin, "symbol", "") or "").upper()
            rate = price_map.get(symbol)
            if not rate:
                continue
            total_balance_map[b.user_id] = total_balance_map.get(b.user_id, 0) + (b.balance * rate)

        # PRE-COMPUTE wallet addresses
        wallet_addresses = WalletAssignment.objects.filter(
            user_id__in=user_ids,
            coin_id__in=coin_ids
        ).values('user_id', 'coin_id', 'wallet_address')
        wallet_map = {(w['user_id'], w['coin_id']): w['wallet_address']
                      for w in wallet_addresses}

        serializer = AdminGetDepositSerializer(
            deposits,
            many=True,
            context={
                "balance_map": balance_map,
                "total_balance_map": total_balance_map,
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

                create_user_notification(
                    user=deposit.user,
                    title="Deposit approved",
                    message=f"Your deposit request #{deposit.id} was approved.",
                    notif_type="deposit_approved",
                    data={"deposit_id": deposit.id},
                )

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

                create_user_notification(
                    user=deposit.user,
                    title="Deposit rejected",
                    message=f"Your deposit request #{deposit.id} was rejected.",
                    notif_type="deposit_rejected",
                    data={"deposit_id": deposit.id},
                )

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


class CreateWithdrawRequestAPI(APIView):
    permission_classes = [IsUser]

    def post(self, request):

        serializer = WithdrawRequestSerializer(data=request.data)

        if serializer.is_valid():

            coin = serializer.validated_data["coin"]
            amount = serializer.validated_data["amount"]
            usd_rate = get_coin_price(getattr(coin, "symbol", ""))

            if usd_rate is None:
                return Response({
                    "error": "Live conversion rate unavailable. Please try again in a moment."
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            convert_amount = (Decimal(amount) / usd_rate).quantize(
                Decimal("0.00000001"),
                rounding=ROUND_DOWN,
            )
            if convert_amount <= 0:
                return Response({
                    "error": "Amount is too small after conversion."
                }, status=400)

            try:
                with transaction.atomic():

                    balance = WalletBalance.objects.select_for_update().get(
                        user=request.user,
                        coin=coin
                    )

                    if balance.balance < amount:
                        return Response({
                            "error": "Insufficient balance"
                        }, status=400)

                    # deduct balance immediately
                    balance.balance -= amount
                    balance.save()

                    withdraw = serializer.save(
                        user=request.user,
                        convert_amount=convert_amount,
                    )

                    Transaction.objects.create(
                        user=request.user,
                        coin=coin,
                        amount=amount,
                        reference=f"Withdraw request Id {withdraw.id}",
                        transaction_type="withdraw",
                        status="pending"
                    )

            except WalletBalance.DoesNotExist:
                return Response({
                    "error": "No balance available"
                }, status=400)

            create_admin_notification(
                title="New withdraw request",
                message=f"User {request.user.email} requested withdraw #{withdraw.id}.",
                notif_type="withdraw_requested",
                data={"withdraw_id": withdraw.id},
            )
            create_user_notification(
                user=request.user,
                title="Withdraw request submitted",
                message=f"Your withdraw request #{withdraw.id} was submitted.",
                notif_type="withdraw_requested",
                data={"withdraw_id": withdraw.id},
            )

            return Response({
                "message": "Withdraw request submitted",
                "data": WithdrawRequestSerializer(withdraw).data
            }, status=201)

        return Response(serializer.errors, status=400)


class MyWithdrawRequestsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        withdraws = WithdrawRequest.objects.filter(
            user=request.user
        ).order_by("-created_at")

        serializer = WithdrawRequestSerializer(withdraws, many=True)

        return Response(serializer.data)


class AdminWithdrawListAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):

        withdraws = WithdrawRequest.objects.select_related(
            "user", "coin", "network"
        ).order_by("-created_at")

        user_ids = set(w.user_id for w in withdraws)
        coin_ids = set(w.coin_id for w in withdraws)

        balances = WalletBalance.objects.filter(
            user_id__in=user_ids
        ).select_related("coin")

        symbols = {
            (getattr(b.coin, "symbol", "") or "").upper()
            for b in balances
        }
        price_map = get_coin_prices(symbols) if symbols else {}

        total_balance_map = {}
        for b in balances:
            symbol = (getattr(b.coin, "symbol", "") or "").upper()
            rate = price_map.get(symbol)
            if not rate:
                continue
            total_balance_map[b.user_id] = total_balance_map.get(b.user_id, 0) + (b.balance * rate)

        serializer = AdminWithdrawSerializer(
            withdraws,
            many=True,
            context={
                "total_balance_map": total_balance_map,
            }
        )

        return Response({
            "message": "All withdraw requests retrieved",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class AdminWithdrawActionAPI(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):

        action = request.data.get("action")

        try:
            withdraw = WithdrawRequest.objects.select_related(
                "user", "coin"
            ).get(pk=pk)

            if withdraw.status != "pending":
                return Response({"error": "Already processed"}, status=400)

            with transaction.atomic():

                if action == "approve":

                    withdraw.status = "approved"
                    withdraw.save()

                    Transaction.objects.filter(
                        reference=f"Withdraw request Id {withdraw.id}"
                    ).update(status="success")

                    create_user_notification(
                        user=withdraw.user,
                        title="Withdraw approved",
                        message=f"Your withdraw request #{withdraw.id} was approved.",
                        notif_type="withdraw_approved",
                        data={"withdraw_id": withdraw.id},
                    )

                    return Response({"message": "Withdraw approved"})

                elif action == "reject":

                    balance = WalletBalance.objects.select_for_update().get(
                        user=withdraw.user,
                        coin=withdraw.coin
                    )

                    balance.balance += withdraw.amount
                    balance.save()

                    withdraw.status = "rejected"
                    withdraw.save()

                    Transaction.objects.filter(
                        reference=f"Withdraw request Id {withdraw.id}"
                    ).update(status="failed")

                    create_user_notification(
                        user=withdraw.user,
                        title="Withdraw rejected",
                        message=f"Your withdraw request #{withdraw.id} was rejected.",
                        notif_type="withdraw_rejected",
                        data={"withdraw_id": withdraw.id},
                    )

                    return Response({"message": "Withdraw rejected"})

                return Response({"error": "Invalid action"}, status=400)

        except WithdrawRequest.DoesNotExist:
            return Response({"error": "Withdraw not found"}, status=404)
