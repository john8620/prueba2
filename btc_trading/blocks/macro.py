"""Bloque 6 — Macro: DXY, Nasdaq, yields, VIX, liquidez global (Fed net liquidity)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import combine_frame, rolling_z, squash
from . import BlockResult, last_row

WEIGHTS = {"c_dxy": 0.25, "c_nasdaq": 0.20, "c_yields": 0.15, "c_vix": 0.15, "c_liquidity": 0.25}


def daily(data: dict) -> pd.DataFrame:
    mc = data.get("macro")
    if mc is None or mc.empty:
        return pd.DataFrame()
    mc = mc.shift(1)  # publicación con retraso -> sin look-ahead
    out = pd.DataFrame(index=mc.index)
    if "dxy" in mc:
        out["dxy"] = mc["dxy"]
        out["c_dxy"] = -squash(rolling_z(mc["dxy"].pct_change(20, fill_method=None), 365, 60), 2)
    if "nasdaq" in mc:
        out["nasdaq"] = mc["nasdaq"]
        out["c_nasdaq"] = squash(rolling_z(mc["nasdaq"].pct_change(20, fill_method=None), 365, 60), 2)
    if "us10y" in mc:
        out["us10y"] = mc["us10y"]
        out["c_yields"] = -squash(rolling_z(mc["us10y"].diff(20), 365, 60), 2)
    if "vix" in mc:
        out["vix"] = mc["vix"]
        out["c_vix"] = -squash(rolling_z(mc["vix"], 365, 60), 2)
    if "net_liquidity" in mc:
        out["net_liquidity_bn"] = mc["net_liquidity"]
        out["c_liquidity"] = squash(rolling_z(mc["net_liquidity"].pct_change(28, fill_method=None), 365, 60), 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    if m.get("vix", 0) > 30:
        notes.append("VIX > 30: entorno risk-off.")
    return BlockResult("macro", m.get("score", np.nan), comps, m, notes)
