"""Adaptador opcional para Binance (misma interfaz que OKX).

Nota: Binance bloquea algunas regiones (HTTP 451). Selecciónalo con
BTC_EXCHANGE=binance si tu IP tiene acceso.
"""
from __future__ import annotations

import pandas as pd

from .http import get

SPOT = "https://api.binance.com/api/v3"
FUT = "https://fapi.binance.com"
_BAR = {"1m": "1m", "5m": "5m", "15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d"}
_PER = {"5m": "5m", "1H": "1h", "4H": "4h", "1D": "1d"}


def _ms(col) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(col), unit="ms", utc=True)


class Binance:
    name = "binance"

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol

    def candles(self, bar: str = "1H", limit: int = 500, inst: str | None = None) -> pd.DataFrame:
        rows: list = []
        end = None
        while len(rows) < limit:
            params = {"symbol": self.symbol, "interval": _BAR[bar], "limit": min(1000, limit - len(rows))}
            if end:
                params["endTime"] = end
            chunk = get(f"{SPOT}/klines", params)
            if not chunk:
                break
            rows = chunk + rows
            end = chunk[0][0] - 1
            if len(chunk) < params["limit"]:
                break
        df = pd.DataFrame(rows).iloc[:, :8]
        df.columns = ["ts", "open", "high", "low", "close", "volume", "close_ts", "quote_volume"]
        df["ts"] = _ms(df["ts"])
        for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[c] = df[c].astype(float)
        return df.drop(columns="close_ts").drop_duplicates("ts").set_index("ts").sort_index()

    def trades(self, limit: int = 1000) -> pd.DataFrame:
        df = pd.DataFrame(get(f"{SPOT}/aggTrades", {"symbol": self.symbol, "limit": limit}, ttl=1))
        df["ts"] = _ms(df["T"])
        df["px"] = df["p"].astype(float)
        df["sz"] = df["q"].astype(float)
        df["side"] = df["m"].map({True: "sell", False: "buy"})  # m=True: comprador es maker
        return df[["ts", "px", "sz", "side"]].set_index("ts")

    def orderbook(self, depth: int = 500) -> dict:
        d = get(f"{SPOT}/depth", {"symbol": self.symbol, "limit": depth}, ttl=0.5)
        return {"bids": [(float(p), float(q)) for p, q in d["bids"]],
                "asks": [(float(p), float(q)) for p, q in d["asks"]],
                "ts": pd.Timestamp.now(tz="UTC")}

    def taker_volume(self, period: str = "1H", inst_type: str = "CONTRACTS") -> pd.DataFrame:
        rows = get(f"{FUT}/futures/data/takerlongshortRatio",
                   {"symbol": self.symbol, "period": _PER[period], "limit": 500})
        df = pd.DataFrame(rows)
        df["ts"] = _ms(df["timestamp"])
        df["buy"] = df["buyVol"].astype(float)
        df["sell"] = df["sellVol"].astype(float)
        return df[["ts", "sell", "buy"]].set_index("ts")

    def open_interest(self, period: str = "1H") -> pd.DataFrame:
        rows = get(f"{FUT}/futures/data/openInterestHist",
                   {"symbol": self.symbol, "period": _PER[period], "limit": 500})
        df = pd.DataFrame(rows)
        df["ts"] = _ms(df["timestamp"])
        df["oi_usd"] = df["sumOpenInterestValue"].astype(float)
        df["volume_usd"] = float("nan")
        return df[["ts", "oi_usd", "volume_usd"]].set_index("ts")

    def funding_history(self, limit: int = 300) -> pd.DataFrame:
        df = pd.DataFrame(get(f"{FUT}/fapi/v1/fundingRate", {"symbol": self.symbol, "limit": min(limit, 1000)}))
        df["ts"] = _ms(df["fundingTime"])
        df["funding"] = df["fundingRate"].astype(float)
        return df[["ts", "funding"]].set_index("ts")

    def current_funding(self) -> float:
        return float(get(f"{FUT}/fapi/v1/premiumIndex", {"symbol": self.symbol}, ttl=5)["lastFundingRate"])

    def long_short_ratio(self, period: str = "1H") -> pd.DataFrame:
        rows = get(f"{FUT}/futures/data/globalLongShortAccountRatio",
                   {"symbol": self.symbol, "period": _PER[period], "limit": 500})
        df = pd.DataFrame(rows)
        df["ts"] = _ms(df["timestamp"])
        df["ls_ratio"] = df["longShortRatio"].astype(float)
        return df[["ts", "ls_ratio"]].set_index("ts")

    def liquidations(self, limit: int = 100) -> pd.DataFrame:
        # Binance retiró el endpoint REST público de liquidaciones (solo websocket forceOrder).
        return pd.DataFrame(columns=["side", "pos_side", "px", "sz", "usd", "liq_type"])

    def basis(self) -> dict:
        p = get(f"{FUT}/fapi/v1/premiumIndex", {"symbol": self.symbol}, ttl=5)
        index, mark = float(p["indexPrice"]), float(p["markPrice"])
        return {"index": index, "perp_mark": mark, "perp_basis": mark / index - 1}
