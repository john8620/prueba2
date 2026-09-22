"""Bloque 4 — Liquidez: Depth, Spread, Amihud, liquidez de stablecoins.

Amihud y stablecoins son direccionales; depth y spread miden la calidad de
ejecución y se devuelven como factor ``quality`` que ajusta el tamaño.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import amihud, combine, combine_frame, depth_usd, rolling_z, spread_bps, squash
from . import BlockResult, last_row

WEIGHTS = {"c_amihud": 0.4, "c_stablecoins": 0.6}


def daily(data: dict) -> pd.DataFrame:
    c = data.get("candles_d")
    if c is None or c.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=c.index)
    out["amihud_30d"] = amihud(c["close"], c["quote_volume"], 30)
    out["c_amihud"] = -squash(rolling_z(out["amihud_30d"], 365, 60), 2)
    st = data.get("stable")
    if st is not None and not st.empty:
        st = st.reindex(out.index.union(st.index)).ffill().reindex(out.index)
        out["stablecoin_mcap"] = st
        out["stablecoin_growth_30d"] = st.pct_change(30, fill_method=None)
        out["c_stablecoins"] = squash(rolling_z(out["stablecoin_growth_30d"], 365, 60), 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    quality = 1.0
    books = data.get("books") or []
    if books:
        bk = books[-1]
        m["spread_bps"] = spread_bps(bk)
        m.update(depth_usd(bk, 0.01))
        if m["spread_bps"] > 5:
            quality *= 0.7
            notes.append(f"Spread amplio ({m['spread_bps']:.1f} bps).")
        if m["depth_usd"] < 5e6:
            quality *= 0.7
            notes.append("Profundidad ±1% < 5M USD: liquidez fina.")
    m["quality"] = quality
    score = combine({k: (comps[k], w) for k, w in WEIGHTS.items()})
    return BlockResult("liquidity", score, comps, m, notes)
