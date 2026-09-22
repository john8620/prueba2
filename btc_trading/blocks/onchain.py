"""Bloque 5 — On-chain: flujos de exchanges, MVRV, SOPR, realized cap.

Si no hay SOPR real (CoinMetrics Pro), se usa un proxy de SOPR de holders de corto
plazo: precio / VWAP de 155 días (coste medio aproximado de monedas "jóvenes").
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import combine_frame, rolling_vwap, rolling_z, squash
from . import BlockResult, last_row

WEIGHTS = {"c_netflow": 0.25, "c_ex_supply": 0.10, "c_mvrv": 0.25, "c_sopr": 0.15, "c_realized_cap": 0.25}


def daily(data: dict) -> pd.DataFrame:
    oc = data.get("onchain")
    if oc is None or oc.empty:
        return pd.DataFrame()
    oc = oc.shift(1)  # los datos de un día se publican al día siguiente -> sin look-ahead
    out = pd.DataFrame(index=oc.index)
    out["mvrv"] = oc["mvrv"]
    out["realized_cap"] = oc["realized_cap"]
    out["ex_netflow_7d"] = oc["ex_netflow"].rolling(7, min_periods=5).sum()
    out["ex_supply"] = oc["ex_supply"]
    out["c_netflow"] = -squash(rolling_z(out["ex_netflow_7d"], 365, 60), 2)
    out["c_ex_supply"] = -squash(rolling_z(oc["ex_supply"].pct_change(30, fill_method=None), 365, 60), 2)
    out["c_mvrv"] = -squash(rolling_z(oc["mvrv"], 1460, 180), 1.5)
    if "sopr" in oc and oc["sopr"].notna().any():
        out["sopr"] = oc["sopr"].rolling(7, min_periods=3).mean()
    else:
        c = data.get("candles_d")
        if c is not None and not c.empty:
            out["sopr"] = (c["close"] / rolling_vwap(c, 155)).reindex(out.index)
    if "sopr" in out:
        out["c_sopr"] = -squash(rolling_z(out["sopr"], 365, 60), 2)
    out["realized_cap_growth_30d"] = oc["realized_cap"].pct_change(30, fill_method=None)
    out["c_realized_cap"] = squash(rolling_z(out["realized_cap_growth_30d"], 365, 60), 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    if m.get("mvrv", 0) > 3.5:
        notes.append("MVRV > 3.5: zona históricamente sobrevalorada.")
    elif 0 < m.get("mvrv", 2) < 1:
        notes.append("MVRV < 1: zona históricamente infravalorada.")
    if data.get("mempool_fees"):
        m["mempool_fastest_fee"] = float(data["mempool_fees"].get("fastestFee", np.nan))
    return BlockResult("onchain", m.get("score", np.nan), comps, m, notes)
