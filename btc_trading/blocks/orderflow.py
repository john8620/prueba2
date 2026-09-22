"""Bloque 2 — Order Flow: CVD, Delta, OFI, Bid/Ask imbalance."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import book_imbalance, combine, combine_frame, ofi, rolling_z, squash, trades_delta
from . import BlockResult, last_row

WEIGHTS = {"c_delta": 0.5, "c_cvd": 0.5}


def daily(data: dict) -> pd.DataFrame:
    t = data.get("taker_d")
    if t is None or t.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=t.index)
    out["delta"] = t["buy"] - t["sell"]
    out["delta_ratio"] = out["delta"] / (t["buy"] + t["sell"])
    out["cvd"] = out["delta"].cumsum()
    out["cvd_7d_slope"] = out["cvd"].diff(7) / (t["buy"] + t["sell"]).rolling(7).sum()
    out["c_delta"] = squash(rolling_z(out["delta_ratio"], 60, 15), 2)
    out["c_cvd"] = squash(rolling_z(out["cvd_7d_slope"], 90, 20), 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    th = data.get("taker_h")
    if th is not None and len(th) > 48:
        dr = (th["buy"] - th["sell"]) / (th["buy"] + th["sell"])
        m["cvd_24h_usd"] = float((th["buy"] - th["sell"]).iloc[-24:].sum())
        m["delta_1h_usd"] = float((th["buy"] - th["sell"]).iloc[-1])
        comps["c_cvd_24h"] = float(squash(rolling_z(dr.rolling(24).mean(), len(dr), 24).iloc[-1], 2))
    tr = data.get("trades")
    if tr is not None and not tr.empty:
        td = trades_delta(tr)
        m.update({f"trades_{k}": v for k, v in td.items()})
        comps["c_trades_delta"] = float(np.clip(td["delta_ratio"], -1, 1) * 0.8)
    books = data.get("books") or []
    if books:
        imb = book_imbalance(books[-1], 0.005)
        m["book_imbalance_0.5pct"] = imb
        comps["c_imbalance"] = float(squash(imb * 3, 1))
    if len(books) > 1:
        top = np.mean([b["bids"][0][1] + b["asks"][0][1] for b in books])
        o = ofi(books)
        m["ofi"] = o
        comps["c_ofi"] = float(squash(o / max(top, 1e-9), 2))
    score = combine({"c_delta": (comps.get("c_delta"), 0.15), "c_cvd": (comps.get("c_cvd"), 0.15),
                     "c_cvd_24h": (comps.get("c_cvd_24h"), 0.25), "c_trades_delta": (comps.get("c_trades_delta"), 0.15),
                     "c_imbalance": (comps.get("c_imbalance"), 0.15), "c_ofi": (comps.get("c_ofi"), 0.15)})
    return BlockResult("orderflow", score, comps, m)
