"""Bloque 1 — Precio: Return, ATR, RV, VWAP."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import atr, combine, combine_frame, realized_vol, rolling_vwap, rolling_z, squash
from . import BlockResult, last_row

WEIGHTS = {"c_trend": 0.40, "c_momentum": 0.30, "c_vwap": 0.30}


def daily(data: dict) -> pd.DataFrame:
    c = data.get("candles_d")
    if c is None or c.empty:
        return pd.DataFrame()
    close = c["close"]
    out = pd.DataFrame(index=c.index)
    out["ret_1d"] = close.pct_change()
    out["ret_7d"] = close.pct_change(7)
    out["ret_30d"] = close.pct_change(30)
    out["atr_14"] = atr(c, 14)
    out["atr_pct"] = out["atr_14"] / close
    out["rv_7d"] = realized_vol(close, 7)
    out["rv_30d"] = realized_vol(close, 30)
    out["rv_ratio"] = out["rv_7d"] / realized_vol(close, 90)
    out["vwap_20d"] = rolling_vwap(c, 20)
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    # Distancia a la EMA50 / VWAP medida en ATRs -> comparable entre regímenes
    out["c_trend"] = squash((close / ema50 - 1) / out["atr_pct"], 3)
    out["c_momentum"] = squash(rolling_z(out["ret_30d"], 365, 60), 2)
    out["c_vwap"] = squash((close / out["vwap_20d"] - 1) / out["atr_pct"], 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    d = daily(data)
    m = last_row(d)
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    h = data.get("candles_h")
    if h is not None and len(h) > 30:
        m["price"] = float(h["close"].iloc[-1])
        m["ret_24h"] = float(h["close"].iloc[-1] / h["close"].iloc[-25] - 1)
        m["rv_24h_ann"] = float(realized_vol(h["close"], 24, 24 * 365).iloc[-1])
        m["atr_1h"] = float(atr(h, 14).iloc[-1])
        vwap_24h = float(rolling_vwap(h, 24).iloc[-1])
        m["vwap_24h"] = vwap_24h
        comps["c_vwap_intraday"] = float(squash((m["price"] / vwap_24h - 1) / (m["atr_1h"] / m["price"]), 3))
    score = combine({**{k: (comps[k], w) for k, w in WEIGHTS.items()},
                     "c_vwap_intraday": (comps.get("c_vwap_intraday", np.nan), 0.20)})
    if m.get("rv_ratio", 1) > 1.5:
        notes.append("Volatilidad en expansión (RV7/RV90 > 1.5): reducir tamaño.")
    return BlockResult("price", score, comps, m, notes)
