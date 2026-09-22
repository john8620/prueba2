"""Liquidez de stablecoins vía DefiLlama (sin clave)."""
from __future__ import annotations

import pandas as pd

from .http import get


def stablecoin_mcap() -> pd.Series:
    rows = get("https://stablecoins.llama.fi/stablecoincharts/all", ttl=3600, timeout=60)
    s = pd.Series({pd.Timestamp(int(r["date"]), unit="s", tz="UTC"):
                   float(r.get("totalCirculatingUSD", {}).get("peggedUSD", 0.0)) for r in rows})
    return s.sort_index().rename("stablecoin_mcap")
