"""Datos de mercado de OKX (API pública, sin clave).

Cubre precio (velas), order flow (trades, taker volume), libro de órdenes y
derivados (OI, funding, basis, liquidaciones, long/short ratio).
"""
from __future__ import annotations

import time

import pandas as pd

from .http import get

BASE = "https://www.okx.com/api/v5"


def _data(path: str, params: dict | None = None, ttl: float = 30.0) -> list:
    js = get(f"{BASE}/{path}", params=params, ttl=ttl)
    if str(js.get("code")) != "0":
        raise RuntimeError(f"OKX {path}: {js.get('msg')}")
    return js["data"]


def _ts(col) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(col), unit="ms", utc=True)


class OKX:
    name = "okx"

    def __init__(self, spot: str = "BTC-USDT", swap: str = "BTC-USDT-SWAP", ccy: str = "BTC"):
        self.spot, self.swap, self.ccy = spot, swap, ccy
        self.uly = swap.replace("-SWAP", "")

    # ---------------- Precio ----------------
    def candles(self, bar: str = "1H", limit: int = 500, inst: str | None = None) -> pd.DataFrame:
        """OHLCV con paginación hacia atrás. `bar`: 1m,5m,15m,1H,4H,1D..."""
        inst = inst or self.spot
        bar = {"1D": "1Dutc", "1W": "1Wutc"}.get(bar, bar)  # velas diarias en UTC
        rows: list = []
        after: str | None = None
        while len(rows) < limit:
            params = {"instId": inst, "bar": bar, "limit": 100}
            if after:
                params["after"] = after
            chunk = _data("market/history-candles", params)
            if not chunk:
                break
            rows.extend(chunk)
            after = chunk[-1][0]
            if len(chunk) < 100:
                break
        df = pd.DataFrame(rows[:limit], columns=["ts", "open", "high", "low", "close", "volume",
                                                 "vol_ccy", "quote_volume", "confirm"])
        df["ts"] = _ts(df["ts"])
        for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[c] = df[c].astype(float)
        return (df.drop(columns=["vol_ccy", "confirm"]).drop_duplicates("ts")
                  .sort_values("ts").set_index("ts"))

    # ---------------- Order flow ----------------
    def trades(self, limit: int = 500) -> pd.DataFrame:
        df = pd.DataFrame(_data("market/trades", {"instId": self.spot, "limit": min(limit, 500)}, ttl=1))
        df["ts"] = _ts(df["ts"])
        df["px"] = df["px"].astype(float)
        df["sz"] = df["sz"].astype(float)
        return df[["ts", "px", "sz", "side"]].sort_values("ts").set_index("ts")

    def orderbook(self, depth: int = 400) -> dict:
        d = _data("market/books", {"instId": self.spot, "sz": depth}, ttl=0.5)[0]
        bids = [(float(p), float(q)) for p, q, *_ in d["bids"]]
        asks = [(float(p), float(q)) for p, q, *_ in d["asks"]]
        return {"bids": bids, "asks": asks, "ts": pd.Timestamp(int(d["ts"]), unit="ms", tz="UTC")}

    def taker_volume(self, period: str = "1H", inst_type: str = "CONTRACTS") -> pd.DataFrame:
        """Volumen agresor comprador/vendedor (USD). Base para Delta y CVD."""
        rows = _data("rubik/stat/taker-volume", {"ccy": self.ccy, "instType": inst_type, "period": period})
        df = pd.DataFrame(rows, columns=["ts", "sell", "buy"])
        df["ts"] = _ts(df["ts"])
        df[["sell", "buy"]] = df[["sell", "buy"]].astype(float)
        return df.sort_values("ts").set_index("ts")

    # ---------------- Derivados ----------------
    def open_interest(self, period: str = "1H") -> pd.DataFrame:
        rows = _data("rubik/stat/contracts/open-interest-volume", {"ccy": self.ccy, "period": period})
        df = pd.DataFrame(rows, columns=["ts", "oi_usd", "volume_usd"])
        df["ts"] = _ts(df["ts"])
        df[["oi_usd", "volume_usd"]] = df[["oi_usd", "volume_usd"]].astype(float)
        return df.sort_values("ts").set_index("ts")

    def funding_history(self, limit: int = 300) -> pd.DataFrame:
        rows: list = []
        after: str | None = None
        while len(rows) < limit:
            params = {"instId": self.swap, "limit": 100}
            if after:
                params["after"] = after
            chunk = _data("public/funding-rate-history", params)
            if not chunk:
                break
            rows.extend(chunk)
            after = chunk[-1]["fundingTime"]
            if len(chunk) < 100:
                break
        df = pd.DataFrame(rows)
        df["ts"] = _ts(df["fundingTime"])
        df["funding"] = df["realizedRate"].replace("", None).fillna(df["fundingRate"]).astype(float)
        return df[["ts", "funding"]].drop_duplicates("ts").sort_values("ts").set_index("ts")

    def current_funding(self) -> float:
        return float(_data("public/funding-rate", {"instId": self.swap}, ttl=5)[0]["fundingRate"])

    def long_short_ratio(self, period: str = "1H") -> pd.DataFrame:
        rows = _data("rubik/stat/contracts/long-short-account-ratio", {"ccy": self.ccy, "period": period})
        df = pd.DataFrame(rows, columns=["ts", "ls_ratio"])
        df["ts"] = _ts(df["ts"])
        df["ls_ratio"] = df["ls_ratio"].astype(float)
        return df.sort_values("ts").set_index("ts")

    def liquidations(self, limit: int = 100) -> pd.DataFrame:
        """Liquidaciones recientes del perpetuo. side=sell -> long liquidado."""
        data = _data("public/liquidation-orders",
                     {"instType": "SWAP", "uly": self.uly, "state": "filled", "limit": limit}, ttl=10)
        rows = []
        for block in data:
            for d in block.get("details", []):
                rows.append({"ts": int(d["ts"]), "side": d["side"], "pos_side": d["posSide"],
                             "px": float(d["bkPx"]), "sz": float(d["sz"])})
        df = pd.DataFrame(rows, columns=["ts", "side", "pos_side", "px", "sz"])
        if df.empty:
            return df
        df["ts"] = _ts(df["ts"])
        # 1 contrato BTC-USDT-SWAP = 0.01 BTC
        df["usd"] = df["px"] * df["sz"] * 0.01
        df["liq_type"] = df["side"].map({"sell": "long", "buy": "short"})
        return df.sort_values("ts").set_index("ts")

    def basis(self) -> dict:
        """Basis del perpetuo (mark vs índice) y basis anualizado del futuro trimestral."""
        index = float(_data("market/index-tickers", {"instId": self.uly.replace("USDT", "USD")}, ttl=5)[0]["idxPx"])
        mark = float(_data("public/mark-price", {"instId": self.swap}, ttl=5)[0]["markPx"])
        out = {"index": index, "perp_mark": mark, "perp_basis": mark / index - 1}
        try:
            insts = _data("public/instruments", {"instType": "FUTURES", "uly": self.uly}, ttl=3600)
            quarter = [i for i in insts if i.get("alias") == "quarter"]
            inst = quarter[0] if quarter else max(insts, key=lambda i: int(i["expTime"]))
            px = float(_data("market/ticker", {"instId": inst["instId"]}, ttl=5)[0]["last"])
            days = (int(inst["expTime"]) / 1000 - time.time()) / 86400
            out.update({"future": inst["instId"], "future_px": px, "days_to_expiry": days,
                        "basis_annualized": (px / index - 1) * 365 / max(days, 1)})
        except Exception:  # noqa: BLE001 - el futuro trimestral es opcional
            pass
        return out
