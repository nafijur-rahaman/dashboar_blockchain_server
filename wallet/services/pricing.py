from datetime import timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.utils import timezone

from wallet.models import CoinPrice, CryptoCoin

COINGECKO_ID_BY_SYMBOL = {
    "BTC": "bitcoin",
    "BITCOIN": "bitcoin",
    "ETH": "ethereum",
    "ETHEREUM": "ethereum",
    "ETC": "ethereum-classic",
    "ETHEREUMCLASSIC": "ethereum-classic",
    "ETHEREUM_CLASSIC": "ethereum-classic",
    "USDT": "tether",
    "TETHER": "tether",
}


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").upper().replace(" ", "").replace("-", "").replace("/", "_")


def fetch_live_prices(symbols):
    normalized_symbols = {_normalize_symbol(symbol) for symbol in symbols if symbol}
    if not normalized_symbols:
        return {}

    ids = {
        COINGECKO_ID_BY_SYMBOL.get(symbol)
        for symbol in normalized_symbols
        if symbol in COINGECKO_ID_BY_SYMBOL and symbol != "USDT"
    }
    if not ids and "USDT" not in normalized_symbols:
        return {}

    # Skip external call if only USDT is requested.
    if not ids and "USDT" in normalized_symbols:
        return {"USDT": Decimal("1")}

    if not ids:
        return {}

    params = {
        "ids": ",".join(sorted(ids)),
        "vs_currencies": "usd",
    }

    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params=params,
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json() or {}

    price_map = {}
    for symbol in normalized_symbols:
        if symbol == "USDT":
            price_map["USDT"] = Decimal("1")
            continue

        coin_id = COINGECKO_ID_BY_SYMBOL.get(symbol)
        usd_value = payload.get(coin_id or "", {}).get("usd")
        if usd_value is None:
            continue

        try:
            usd_rate = Decimal(str(usd_value))
        except (InvalidOperation, ValueError, TypeError):
            continue

        if usd_rate > 0:
            price_map[symbol] = usd_rate

    return price_map


def _cache_prices(price_map):
    if not price_map:
        return

    coins = CryptoCoin.objects.filter(symbol__in=price_map.keys())
    coins_by_symbol = {coin.symbol.upper(): coin for coin in coins}

    for symbol, price in price_map.items():
        coin = coins_by_symbol.get(symbol)
        if not coin:
            continue
        CoinPrice.objects.update_or_create(
            coin=coin,
            defaults={"price_usdt": price},
        )


def _get_cached_prices(symbols, max_age_seconds=None):
    if not symbols:
        return {}

    symbols = {symbol for symbol in symbols if symbol}
    if not symbols:
        return {}

    coins = CryptoCoin.objects.filter(symbol__in=symbols)
    if not coins:
        return {}

    cached_qs = CoinPrice.objects.filter(coin__in=coins).select_related("coin")
    if max_age_seconds is not None:
        cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
        cached_qs = cached_qs.filter(updated_at__gte=cutoff)

    price_map = {}
    for cached in cached_qs:
        price_map[cached.coin.symbol.upper()] = cached.price_usdt

    if "USDT" in symbols and "USDT" not in price_map:
        price_map["USDT"] = Decimal("1")

    return price_map


def get_coin_price(symbol):
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return None

    max_age_seconds = getattr(settings, "COIN_PRICE_CACHE_MAX_AGE_SECONDS", 300)
    cached = _get_cached_prices([normalized_symbol], max_age_seconds=max_age_seconds)
    if normalized_symbol in cached:
        return cached[normalized_symbol]

    try:
        live = fetch_live_prices([normalized_symbol])
        price = live.get(normalized_symbol)
        if price is not None:
            _cache_prices(live)
            return price
    except requests.RequestException:
        pass
    except Exception:
        pass

    try:
        coin = CryptoCoin.objects.get(symbol=normalized_symbol)
        cached = CoinPrice.objects.get(coin=coin)
        return cached.price_usdt
    except (CryptoCoin.DoesNotExist, CoinPrice.DoesNotExist):
        return None


def get_coin_prices(symbols):
    normalized_symbols = [
        _normalize_symbol(symbol) for symbol in symbols if symbol
    ]
    normalized_symbols = [symbol for symbol in normalized_symbols if symbol]
    if not normalized_symbols:
        return {}

    max_age_seconds = getattr(settings, "COIN_PRICE_CACHE_MAX_AGE_SECONDS", 300)
    cached_fresh = _get_cached_prices(normalized_symbols, max_age_seconds=max_age_seconds)
    if len(cached_fresh) == len(set(normalized_symbols)):
        return cached_fresh

    price_map = {}
    try:
        live = fetch_live_prices(normalized_symbols)
        if live:
            _cache_prices(live)
            price_map.update(live)
    except requests.RequestException:
        pass
    except Exception:
        pass

    missing = [symbol for symbol in normalized_symbols if symbol not in price_map]
    if not missing:
        return price_map

    cached_any = _get_cached_prices(missing)
    price_map.update(cached_any)

    return price_map
