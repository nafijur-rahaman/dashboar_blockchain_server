from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from decimal import Decimal, ROUND_DOWN, InvalidOperation
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone

from wallet.models import CryptoCoin, WalletAssignment
from wallet.services.pricing import get_coin_prices
from wallet.services.pricing import get_coin_price
from .models import DepositRequest, WalletBalance, Transaction, WithdrawRequest
from .serializers import BalanceAdjustmentSerializer, DepositRequestSerializer, WalletBalanceSerializer, TransactionSerializer, AdminGetDepositSerializer, WithdrawRequestSerializer, AdminWithdrawSerializer

from users.permissions import IsAdmin, IsUser, IsAdminOrUser
from users.models import User
from tickets.models import Ticket
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
        symbols.update(
            (getattr(d.coin, "symbol", "") or "").upper()
            for d in deposits
            if d.coin_id
        )
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
                "wallet_map": wallet_map,
                "price_map": price_map,
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

                    # Compare against coin balance using converted coin amount
                    if balance.balance < convert_amount:
                        return Response({
                            "error": "Insufficient balance"
                        }, status=400)

                    # deduct balance immediately
                    balance.balance -= convert_amount
                    balance.save(update_fields=["balance"])

                    withdraw = serializer.save(
                        user=request.user,
                        convert_amount=convert_amount,
                    )

                    Transaction.objects.create(
                        user=request.user,
                        coin=coin,
                        amount=convert_amount,
                        reference=f"Withdraw request Id {withdraw.id}",
                        transaction_type="withdraw",
                        status="pending"
                    )

            except WalletBalance.DoesNotExist:
                return Response({
                    "error": "No balance available"
                }, status=400)

            amount_usd = amount
            coin_symbol = (getattr(coin, "symbol", "") or "").upper()
            network_name = getattr(
                serializer.validated_data.get("network"), "network_name", ""
            )
            wallet_address = serializer.validated_data.get("wallet_address", "")
            address_short = (
                f"{wallet_address[:6]}...{wallet_address[-4:]}"
                if wallet_address and len(wallet_address) > 12
                else wallet_address
            )

            create_admin_notification(
                title="New withdraw request",
                message=(
                    f"Withdraw requested: {request.user.email} requested "
                    f"{amount_usd} USD (~{convert_amount} {coin_symbol}) "
                    f"on {network_name or 'network'}. Wallet: {address_short}."
                ),
                notif_type="withdraw_requested",
                data={"withdraw_id": withdraw.id},
            )
            create_user_notification(
                user=request.user,
                title="Withdraw request submitted",
                message=(
                    f"Your withdrawal request of {amount_usd} USD "
                    f"(~{convert_amount} {coin_symbol}) on "
                    f"{network_name or 'network'} was submitted."
                ),
                notif_type="withdraw_requested",
                data={"withdraw_id": withdraw.id},
            )

            return Response({
                "message": "Withdraw request submitted",
                "data": WithdrawRequestSerializer(withdraw).data
            }, status=201)

        return Response(serializer.errors, status=400)


class WithdrawQuoteAPI(APIView):
    permission_classes = [IsUser]

    def post(self, request):
        coin_id = request.data.get("coin")
        amount = request.data.get("amount")

        if not coin_id:
            return Response({"error": "Coin is required"}, status=400)

        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid amount"}, status=400)

        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)

        try:
            coin = CryptoCoin.objects.get(id=coin_id)
        except CryptoCoin.DoesNotExist:
            return Response({"error": "Coin not found"}, status=404)

        usd_rate = get_coin_price(getattr(coin, "symbol", ""))
        if usd_rate is None:
            return Response(
                {"error": "Live conversion rate unavailable. Please try again in a moment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        convert_amount = (amount / usd_rate).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )

        if convert_amount <= 0:
            return Response({"error": "Amount is too small after conversion."}, status=400)

        return Response(
            {
                "coin_symbol": (getattr(coin, "symbol", "") or "").upper(),
                "amount_usd": str(amount),
                "rate_usd": str(usd_rate),
                "convert_amount": str(convert_amount),
            },
            status=status.HTTP_200_OK,
        )


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
                        message=(
                            f"Your withdrawal of {withdraw.amount} USD "
                            f"(~{withdraw.convert_amount} "
                            f"{(withdraw.coin.symbol or '').upper()}) on "
                            f"{getattr(withdraw.network, 'network_name', '') or 'network'} "
                            f"was approved."
                        ),
                        notif_type="withdraw_approved",
                        data={"withdraw_id": withdraw.id},
                    )

                    return Response({"message": "Withdraw approved"})

                elif action == "reject":

                    balance = WalletBalance.objects.select_for_update().get(
                        user=withdraw.user,
                        coin=withdraw.coin
                    )

                    refund_amount = withdraw.convert_amount if withdraw.convert_amount is not None else withdraw.amount
                    balance.balance += refund_amount
                    balance.save(update_fields=["balance"])

                    withdraw.status = "rejected"
                    withdraw.save()

                    Transaction.objects.filter(
                        reference=f"Withdraw request Id {withdraw.id}"
                    ).update(status="failed")

                    create_user_notification(
                        user=withdraw.user,
                        title="Withdraw rejected",
                        message=(
                            f"Your withdrawal of {withdraw.amount} USD "
                            f"(~{withdraw.convert_amount} "
                            f"{(withdraw.coin.symbol or '').upper()}) on "
                            f"{getattr(withdraw.network, 'network_name', '') or 'network'} "
                            f"was rejected. The {refund_amount} "
                            f"{(withdraw.coin.symbol or '').upper()} has been returned to your balance."
                        ),
                        notif_type="withdraw_rejected",
                        data={"withdraw_id": withdraw.id},
                    )

                    return Response({"message": "Withdraw rejected"})

                return Response({"error": "Invalid action"}, status=400)

        except WithdrawRequest.DoesNotExist:
            return Response({"error": "Withdraw not found"}, status=404)


class AdminDashboardStatsAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        today = timezone.localdate()

        # ---- Users ----
        users_qs = User.objects.filter(role="user")
        total_users = users_qs.count()
        new_users_today = users_qs.filter(date_joined__date=today).count()

        # ---- Wallet balances ----
        balance_rows = (
            WalletBalance.objects.filter(user__role="user")
            .values("coin__symbol")
            .annotate(total=Sum("balance"))
        )
        balance_symbols = [row["coin__symbol"] for row in balance_rows if row["coin__symbol"]]

        # ---- Pending deposits/withdrawals and latest transactions ----
        pending_withdraw_rows = (
            WithdrawRequest.objects.filter(status="pending")
            .values("coin__symbol")
            .annotate(total=Sum("amount"), count=Count("id"))
        )
        pending_deposit_rows = (
            DepositRequest.objects.filter(status="pending")
            .values("coin__symbol")
            .annotate(total=Sum("amount"), count=Count("id"))
        )
        todays_deposit_rows = (
            DepositRequest.objects.filter(status="approved", created_at__date=today)
            .values("coin__symbol")
            .annotate(total=Sum("amount"), count=Count("id"))
        )
        latest_withdraws = WithdrawRequest.objects.select_related("user", "coin").order_by("-created_at")[:5]
        recent_transactions = Transaction.objects.select_related("user", "coin").order_by("-created_at")[:7]

        # ---- Collect all unique symbols for one get_coin_prices call ----
        symbols = set(balance_symbols)
        symbols.update(row['coin__symbol'] for row in pending_withdraw_rows if row['coin__symbol'])
        symbols.update(row['coin__symbol'] for row in pending_deposit_rows if row['coin__symbol'])
        symbols.update(row['coin__symbol'] for row in todays_deposit_rows if row['coin__symbol'])
        symbols.update(w.coin.symbol for w in latest_withdraws if w.coin_id)
        symbols.update(tx.coin.symbol for tx in recent_transactions if tx.coin_id)

        price_map = get_coin_prices(symbols) if symbols else {}

        # ---- Helper function ----
        def summarize_amounts(rows):
            total_count = 0
            total_usd = Decimal("0")
            for row in rows:
                symbol = (row["coin__symbol"] or "").upper()
                amount = row["total"] or Decimal("0")
                count = row.get("count", 0) or 0
                rate = price_map.get(symbol)
                usd_value = amount * rate if rate else Decimal("0")
                total_count += count
                total_usd += usd_value
            return total_count, total_usd
        
        # Withdraw amounts are already in USD in this system
        def summarize_usd_amounts(rows):
            total_count = 0
            total_usd = Decimal("0")
            for row in rows:
                amount = row["total"] or Decimal("0")
                count = row.get("count", 0) or 0
                total_count += count
                total_usd += amount
            return total_count, total_usd

        # ---- Summaries ----
        total_balance_usd = Decimal("0")
        coin_balances_raw = []
        for row in balance_rows:
            symbol = (row["coin__symbol"] or "").upper()
            amount = row["total"] or Decimal("0")
            rate = price_map.get(symbol)
            usd_value = amount * rate if rate else Decimal("0")
            total_balance_usd += usd_value
            coin_balances_raw.append({
                "symbol": symbol,
                "amount": amount,
                "usd_value": usd_value
            })

        coin_balances_raw.sort(key=lambda item: item["usd_value"], reverse=True)
        coin_balances = [{"symbol": item["symbol"], "amount": str(item["amount"])} for item in coin_balances_raw[:3]]

        pending_withdraw_count, pending_withdraw_usd = summarize_usd_amounts(pending_withdraw_rows)
        pending_deposit_count, pending_deposit_usd = summarize_amounts(pending_deposit_rows)
        _, todays_deposits_usd = summarize_amounts(todays_deposit_rows)

        # ---- Tickets ----
        tickets_qs = Ticket.objects.select_related("user").order_by("-updated_at")[:5]
        tickets_payload = [
            {
                "id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            }
            for ticket in tickets_qs
        ]

        # ---- Latest withdrawals ----
        latest_withdrawals_payload = []
        for withdraw in latest_withdraws:
            amount_usd = withdraw.amount
            latest_withdrawals_payload.append({
                "id": withdraw.id,
                "user_id": withdraw.user_id,
                "user_name": withdraw.user.full_name or "",
                "user_email": withdraw.user.email,
                "coin_symbol": (withdraw.coin.symbol or "").upper(),
                "amount_usd": str(amount_usd),
                "status": withdraw.status,
                "created_at": withdraw.created_at.isoformat() if withdraw.created_at else None,
            })

        # ---- Recent transactions ----
        recent_transactions_payload = []
        for tx in recent_transactions:
            symbol = (tx.coin.symbol or "").upper()
            rate = price_map.get(symbol)
            amount_usd = tx.amount * rate if rate else Decimal("0")
            recent_transactions_payload.append({
                "id": tx.id,
                "user_id": tx.user_id,
                "user_name": tx.user.full_name or "",
                "user_email": tx.user.email,
                "coin_symbol": symbol,
                "amount_usd": str(amount_usd),
                "status": tx.status,
                "transaction_type": tx.transaction_type,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            })

        return Response({
            "summary": {
                "total_users": total_users,
                "new_users_today": new_users_today,
                "total_balance_usd": str(total_balance_usd),
                "todays_deposits_usd": str(todays_deposits_usd),
                "pending_withdrawals_count": pending_withdraw_count,
                "pending_withdrawals_usd": str(pending_withdraw_usd),
                "pending_deposits_count": pending_deposit_count,
                "pending_deposits_usd": str(pending_deposit_usd),
            },
            "coin_balances": coin_balances,
            "tickets": tickets_payload,
            "latest_withdrawals": latest_withdrawals_payload,
            "recent_transactions": recent_transactions_payload,
        }, status=status.HTTP_200_OK)


class AdminTransactionDetailAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            tx = Transaction.objects.select_related("user", "coin").get(pk=pk)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "id": tx.id,
            "user_id": tx.user_id,
            "user_name": tx.user.full_name or "",
            "user_email": tx.user.email,
            "user_status": tx.user.status,
            "coin_symbol": getattr(tx.coin, "symbol", ""),
            "amount": str(tx.amount),
            "transaction_type": tx.transaction_type,
            "status": tx.status,
            "reference": tx.reference,
            "internal_note": tx.internal_note,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }, status=status.HTTP_200_OK)


class AdminWithdrawDetailAPI(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            withdraw = WithdrawRequest.objects.select_related(
                "user", "coin", "network"
            ).get(pk=pk)
        except WithdrawRequest.DoesNotExist:
            return Response({"error": "Withdraw request not found"}, status=status.HTTP_404_NOT_FOUND)

        balances = WalletBalance.objects.filter(
            user_id=withdraw.user_id
        ).select_related("coin")

        symbols = {
            (getattr(b.coin, "symbol", "") or "").upper()
            for b in balances
        }
        price_map = get_coin_prices(symbols) if symbols else {}

        total_balance = Decimal("0")
        for b in balances:
            symbol = (getattr(b.coin, "symbol", "") or "").upper()
            rate = price_map.get(symbol)
            if not rate:
                continue
            total_balance += (b.balance * rate)

        return Response({
            "id": withdraw.id,
            "user": withdraw.user_id,
            "user_name": withdraw.user.full_name or "",
            "user_email": withdraw.user.email,
            "user_status": withdraw.user.status,
            "user_balance": str(total_balance),
            "coin_symbol": getattr(withdraw.coin, "symbol", ""),
            "network_name": getattr(withdraw.network, "network_name", ""),
            "wallet_address": withdraw.wallet_address,
            "amount": str(withdraw.amount),
            "convert_amount": str(withdraw.convert_amount) if withdraw.convert_amount is not None else None,
            "status": withdraw.status,
            "created_at": withdraw.created_at.isoformat() if withdraw.created_at else None,
        }, status=status.HTTP_200_OK)


class UserDashboardStatsAPI(APIView):
    permission_classes = [IsUser]

    def get(self, request):
        user = request.user

        balances = (
            WalletBalance.objects.filter(user=user)
            .select_related("coin")
        )
        symbols = {
            (getattr(b.coin, "symbol", "") or "").upper()
            for b in balances
        }
        price_map = get_coin_prices(symbols) if symbols else {}

        total_balance_usd = Decimal("0")
        coin_balances = []
        for balance in balances:
            symbol = (getattr(balance.coin, "symbol", "") or "").upper()
            rate = price_map.get(symbol)
            usd_value = balance.balance * rate if rate else Decimal("0")
            total_balance_usd += usd_value
            coin_balances.append({
                "symbol": symbol,
                "amount": str(balance.balance),
                "usd_value": str(usd_value),
            })

        pending_withdrawals = (
            WithdrawRequest.objects.filter(user=user, status="pending")
            .values("coin__symbol")
            .annotate(total=Sum("amount"))
        )
        pending_withdrawals_usd = Decimal("0")
        for row in pending_withdrawals:
            amount = row["total"] or Decimal("0")
            pending_withdrawals_usd += amount

        transactions = (
            Transaction.objects.filter(user=user)
            .select_related("coin")
            .order_by("-created_at")[:8]
        )
        tx_symbols = {tx.coin.symbol.upper() for tx in transactions if tx.coin_id}
        tx_price_map = get_coin_prices(tx_symbols) if tx_symbols else {}

        recent_transactions = []
        for tx in transactions:
            symbol = (tx.coin.symbol or "").upper()
            rate = tx_price_map.get(symbol)
            amount_usd = tx.amount * rate if rate else Decimal("0")
            recent_transactions.append({
                "id": tx.id,
                "coin_symbol": symbol,
                "amount": str(tx.amount),
                "amount_usd": str(amount_usd),
                "transaction_type": tx.transaction_type,
                "status": tx.status,
                "reference": tx.reference,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            })

        return Response({
            "summary": {
                "total_balance_usd": str(total_balance_usd),
                "pending_withdrawals_usd": str(pending_withdrawals_usd),
            },
            "coin_balances": coin_balances,
            "recent_transactions": recent_transactions,
        }, status=status.HTTP_200_OK)
