"""Macro vía FRED (CSV público, sin clave).

DXY -> DTWEXBGS (índice dólar amplio de la Fed, proxy de DXY)
Nasdaq -> NASDAQCOM, 10Y -> DGS10, 2Y -> DGS2, VIX -> VIXCLS
Liquidez (Fed net liquidity) = WALCL - WTREGEN - RRPONTSYD
"""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .http import get

SERIES = {
    "dxy": "DTWEXBGS",
    "nasdaq": "NASDAQCOM",
    "us10y": "DGS10",
    "us2y": "DGS2",
    "vix": "VIXCLS",
    "fed_assets": "WALCL",      # millones USD, semanal
    "tga": "WTREGEN",           # millones USD, semanal
    "rrp": "RRPONTSYD",         # miles de millones USD, diario
}


def fred_series(series_id: str, start: str = "2018-01-01") -> pd.Series:
    txt = get("https://fred.stlouisfed.org/graph/fredgraph.csv",
              {"id": series_id, "cosd": start}, ttl=3600, as_text=True, timeout=60)
    df = pd.read_csv(io.StringIO(txt))
    df.columns = ["date", "value"]
    s = pd.to_numeric(df["value"], errors="coerce")
    s.index = pd.to_datetime(df["date"], utc=True)
    return s.dropna()


def macro_frame(start: str = "2018-01-01") -> pd.DataFrame:
    data = {}
    with ThreadPoolExecutor(max_workers=len(SERIES)) as pool:
        futs = {name: pool.submit(fred_series, sid, start) for name, sid in SERIES.items()}
        for name, fut in futs.items():
            try:
                data[name] = fut.result()
            except Exception:  # noqa: BLE001 - una serie caída no bloquea el resto
                continue
    if not data:
        raise RuntimeError("FRED no disponible")
    df = pd.DataFrame(data).sort_index()
    idx = pd.date_range(df.index.min(), df.index.max(), freq="D", tz="UTC")
    df = df.reindex(df.index.union(idx)).ffill().reindex(idx)
    if {"fed_assets", "tga", "rrp"} <= set(df.columns):
        df["net_liquidity"] = df["fed_assets"] / 1000 - df["tga"] / 1000 - df["rrp"]  # miles de millones
    return df
