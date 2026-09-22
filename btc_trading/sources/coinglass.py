"""CoinGlass API v4 (opcional, requiere COINGLASS_API_KEY).

Aporta datos agregados multi-exchange: OI, liquidaciones, funding ponderado por OI.
Si no hay clave o el plan no cubre el endpoint, las funciones devuelven None y el
sistema sigue con los datos de OKX/Binance.
"""
from __future__ import annotations

import pandas as pd

from .http import get

BASE = "https://open-api-v4.coinglass.com"


def _get(path: str, key: str, params: dict) -> list | None:
    try:
        js = get(f"{BASE}{path}", params=params, headers={"CG-API-KEY": key}, ttl=300)
    except Exception:  # noqa: BLE001
        return None
    if str(js.get("code")) != "0":
        return None
    return js.get("data")


def _frame(rows: list | None, cols: dict[str, str]) -> pd.DataFrame | None:
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(pd.to_numeric(df["time"]), unit="ms", utc=True)
    df = df.set_index("ts").rename(columns=cols)
    return df[list(cols.values())].apply(pd.to_numeric, errors="coerce").sort_index()


def aggregated_oi(key: str, interval: str = "1d", symbol: str = "BTC") -> pd.DataFrame | None:
    rows = _get("/api/futures/open-interest/aggregated-history", key, {"symbol": symbol, "interval": interval})
    return _frame(rows, {"close": "oi_usd"})


def oi_weighted_funding(key: str, interval: str = "1d", symbol: str = "BTC") -> pd.DataFrame | None:
    rows = _get("/api/futures/funding-rate/oi-weight-history", key, {"symbol": symbol, "interval": interval})
    return _frame(rows, {"close": "funding"})


def aggregated_liquidations(key: str, interval: str = "1d", symbol: str = "BTC",
                            exchanges: str = "Binance,OKX,Bybit") -> pd.DataFrame | None:
    rows = _get("/api/futures/liquidation/aggregated-history", key,
                {"symbol": symbol, "interval": interval, "exchange_list": exchanges})
    return _frame(rows, {"aggregated_long_liquidation_usd": "long_liq_usd",
                         "aggregated_short_liquidation_usd": "short_liq_usd"})
