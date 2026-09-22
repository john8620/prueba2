"""Bloque 3 — Derivados: OI, Funding, Basis, Liquidaciones.

- OI + precio: OI subiendo confirma la dirección del precio; OI cayendo resta convicción.
- Funding y basis: contrarian en extremos (posicionamiento apalancado saturado).
- Liquidaciones: cascadas de longs liquidados = capitulación (contrarian alcista) y viceversa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import combine, combine_frame, rolling_z, squash
from . import BlockResult, last_row

WEIGHTS = {"c_oi": 0.35, "c_funding": 0.35, "c_liq": 0.30}
NORMAL_BASIS = 0.08  # basis anualizado "normal" del trimestral (~8%)


def daily(data: dict) -> pd.DataFrame:
    c = data.get("candles_d")
    if c is None or c.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=c.index)
    ret7 = c["close"].pct_change(7)
    oi = data.get("oi_d")
    if oi is not None and not oi.empty:
        out["oi_usd"] = oi["oi_usd"].reindex(out.index)
        out["oi_chg_7d"] = out["oi_usd"].pct_change(7, fill_method=None)
        out["c_oi"] = squash(ret7 / 0.05, 1) * (0.5 + 0.5 * squash(out["oi_chg_7d"] / 0.10, 1))
    f = data.get("funding_d")
    if f is not None and not f.empty:
        out["funding_daily"] = f["funding"].reindex(out.index)
        out["funding_7d"] = out["funding_daily"].rolling(7, min_periods=3).mean()
        out["funding_ann"] = out["funding_7d"] * 365
        out["c_funding"] = -squash(rolling_z(out["funding_7d"], 180, 30), 2)
    lq = data.get("liq_d")
    if lq is not None and not lq.empty:
        lq = lq.reindex(out.index)
        tot = lq["long_liq_usd"] + lq["short_liq_usd"]
        share = (lq["long_liq_usd"] - lq["short_liq_usd"]) / tot.replace(0, np.nan)
        intensity = squash(rolling_z(tot, 90, 20).clip(lower=0), 1)
        out["liq_total_usd"] = tot
        out["c_liq"] = share * (0.3 + 0.7 * intensity)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    b = data.get("basis") or {}
    if b:
        m.update({k: v for k, v in b.items() if isinstance(v, (int, float))})
        if "basis_annualized" in b:
            comps["c_basis"] = float(-squash((b["basis_annualized"] - NORMAL_BASIS) / 0.10, 1))
        else:
            comps["c_basis"] = float(-squash(b["perp_basis"] / 0.001, 2))
    if data.get("funding_now") is not None:
        m["funding_now_8h"] = data["funding_now"]
        if abs(data["funding_now"]) > 0.0005:
            notes.append("Funding extremo (>0.05%/8h): riesgo de squeeze.")
    lq = data.get("liqs")
    if lq is not None and not lq.empty and np.isnan(comps.get("c_liq", np.nan)):
        recent = lq[lq.index > lq.index.max() - pd.Timedelta(hours=24)]
        lu = recent.loc[recent["liq_type"] == "long", "usd"].sum()
        su = recent.loc[recent["liq_type"] == "short", "usd"].sum()
        m.update({"liq_long_usd_recent": float(lu), "liq_short_usd_recent": float(su)})
        if lu + su > 0:
            comps["c_liq"] = float((lu - su) / (lu + su) * 0.5)
    score = combine({"c_oi": (comps.get("c_oi"), 0.30), "c_funding": (comps.get("c_funding"), 0.25),
                     "c_basis": (comps.get("c_basis"), 0.20), "c_liq": (comps.get("c_liq"), 0.25)})
    return BlockResult("derivatives", score, comps, m, notes)
