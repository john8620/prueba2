"""Bloque 7 — Psicología: Fear & Greed, sentimiento de noticias, social volume, posicionamiento.

Fear & Greed y posicionamiento (long/short ratio) son contrarian: la multitud
extrema suele equivocarse. El volumen social (nº de titulares / trending) amplifica
la señal contrarian cuando la atención es alta.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features import combine, combine_frame, rolling_z, squash
from . import BlockResult, last_row

WEIGHTS = {"c_fear_greed": 0.6, "c_positioning": 0.4}


def fg_component(fg):
    """Contrarian no lineal: casi neutro en 30-70, fuerte en los extremos."""
    x = (fg - 50) / 50
    return -np.clip(1.6 * x ** 3, -1, 1)


def daily(data: dict) -> pd.DataFrame:
    fg = data.get("fng")
    ls = data.get("ls_d")
    idx = None
    for s in (fg, ls):
        if s is not None and len(s):
            idx = s.index if idx is None else idx.union(s.index)
    if idx is None:
        return pd.DataFrame()
    out = pd.DataFrame(index=idx)
    if fg is not None and len(fg):
        out["fear_greed"] = fg.reindex(idx)
        out["c_fear_greed"] = fg_component(out["fear_greed"])
    if ls is not None and len(ls):
        out["ls_ratio"] = ls["ls_ratio"].reindex(idx)
        out["c_positioning"] = -squash(rolling_z(out["ls_ratio"], 90, 20), 2)
    out["score"] = combine_frame(out, WEIGHTS)
    return out


def live(data: dict) -> BlockResult:
    m = last_row(daily(data))
    comps = {k: m.get(k, np.nan) for k in WEIGHTS}
    notes = []
    lh = data.get("ls_h")
    if lh is not None and len(lh) > 24:
        m["ls_ratio_now"] = float(lh["ls_ratio"].iloc[-1])
        comps["c_positioning"] = float(-squash(rolling_z(lh["ls_ratio"], len(lh), 24).iloc[-1], 2))
    news = data.get("news")
    attention = 0.0
    if news is not None and not news.empty:
        m["news_count_24h"] = float(len(news))
        m["news_sentiment"] = float(news["score"].mean())
        comps["c_news"] = float(squash(m["news_sentiment"] * 3, 1))
        attention = min(len(news) / 30, 1.0)
    rank = data.get("trending_rank")
    if rank:
        m["coingecko_trending_rank"] = float(rank)
        attention = max(attention, 1 - (rank - 1) / 15)
    m["social_attention"] = attention
    if np.isfinite(comps.get("c_fear_greed", np.nan)):
        comps["c_fear_greed"] = float(np.clip(comps["c_fear_greed"] * (1 + 0.5 * attention), -1, 1))
    fg = m.get("fear_greed", 50)
    if fg >= 80:
        notes.append("Codicia extrema: riesgo de techo local.")
    elif fg <= 20:
        notes.append("Miedo extremo: posible zona de capitulación.")
    score = combine({"c_fear_greed": (comps.get("c_fear_greed"), 0.4),
                     "c_positioning": (comps.get("c_positioning"), 0.3),
                     "c_news": (comps.get("c_news"), 0.3)})
    return BlockResult("sentiment", score, comps, m, notes)
