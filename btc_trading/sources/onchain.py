"""On-chain: CoinMetrics Community API (gratis) y mempool.space.

Métricas: flujos de exchanges, MVRV, market cap y realized cap (= mcap / MVRV).
SOPR no está en el plan gratuito; si defines COINMETRICS_API_KEY se usa el real,
si no, el bloque on-chain calcula un proxy (ver blocks/onchain.py).
"""
from __future__ import annotations

import os

import pandas as pd

from .http import get

CM_COMMUNITY = "https://community-api.coinmetrics.io/v4"
CM_PRO = "https://api.coinmetrics.io/v4"
FREE_METRICS = ["CapMVRVCur", "CapMrktCurUSD", "FlowInExNtv", "FlowOutExNtv", "SplyExNtv", "AdrActCnt", "PriceUSD"]


def coinmetrics(metrics: list[str] | None = None, start: str = "2018-01-01", asset: str = "btc") -> pd.DataFrame:
    key = os.getenv("COINMETRICS_API_KEY")
    base = CM_PRO if key else CM_COMMUNITY
    metrics = list(metrics or FREE_METRICS)
    if key:
        metrics += ["SOPR"]
    params = {"assets": asset, "metrics": ",".join(metrics), "start_time": start,
              "page_size": 10000, "frequency": "1d"}
    if key:
        params["api_key"] = key
    rows: list = []
    url = f"{base}/timeseries/asset-metrics"
    while url:
        js = get(url, params=params, ttl=3600, timeout=60)
        if "error" in js:
            raise RuntimeError(js["error"].get("message"))
        rows.extend(js.get("data", []))
        url, params = js.get("next_page_url"), None
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("ts")[[m for m in metrics if m in df.columns]].apply(pd.to_numeric, errors="coerce")
    df = df.rename(columns={"CapMVRVCur": "mvrv", "CapMrktCurUSD": "mcap", "FlowInExNtv": "ex_inflow",
                            "FlowOutExNtv": "ex_outflow", "SplyExNtv": "ex_supply",
                            "AdrActCnt": "active_addr", "PriceUSD": "price", "SOPR": "sopr"})
    df["realized_cap"] = df["mcap"] / df["mvrv"]
    df["ex_netflow"] = df["ex_inflow"] - df["ex_outflow"]
    return df


def mempool_fees() -> dict:
    """Comisiones recomendadas (sat/vB): proxy de congestión/actividad on-chain."""
    return get("https://mempool.space/api/v1/fees/recommended", ttl=60)
