"""Cálculos cuantitativos reutilizables por los bloques."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------- utilidades de normalización ----------------
def rolling_z(s: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    mp = min_periods or max(10, window // 4)
    mu = s.rolling(window, min_periods=mp).mean()
    sd = s.rolling(window, min_periods=mp).std()
    return (s - mu) / sd.replace(0, np.nan)


def squash(x, k: float = 2.0):
    """Mapea un z-score (o cualquier valor) a [-1, 1] de forma suave."""
    return np.tanh(x / k)


def zscore_last(s: pd.Series, window: int | None = None) -> float:
    s = s.dropna()
    if window:
        s = s.iloc[-window:]
    if len(s) < 5 or s.std() == 0:
        return float("nan")
    return float((s.iloc[-1] - s.mean()) / s.std())


def combine(components: dict[str, tuple[float, float]]) -> float:
    """Media ponderada ignorando componentes NaN. components = {nombre: (valor, peso)}."""
    num = den = 0.0
    for val, w in components.values():
        if val is None or not np.isfinite(val):
            continue
        num += val * w
        den += w
    return float(np.clip(num / den, -1, 1)) if den else float("nan")


def combine_frame(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    cols = [c for c in weights if c in df]
    w = pd.Series({c: weights[c] for c in cols})
    vals = df[cols]
    mask = vals.notna()
    num = (vals.fillna(0) * w).sum(axis=1)
    den = (mask * w).sum(axis=1)
    return (num / den.replace(0, np.nan)).clip(-1, 1)


# ---------------- 1. Precio ----------------
def returns(close: pd.Series, n: int = 1) -> pd.Series:
    return close.pct_change(n)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift()
    return pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def realized_vol(close: pd.Series, n: int, periods_per_year: float = 365) -> pd.Series:
    """Volatilidad realizada anualizada (desviación de log-retornos)."""
    lr = np.log(close).diff()
    return lr.rolling(n, min_periods=max(2, n // 2)).std() * np.sqrt(periods_per_year)


def rolling_vwap(df: pd.DataFrame, n: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"]
    return (tp * vol).rolling(n, min_periods=max(2, n // 2)).sum() / vol.rolling(n, min_periods=max(2, n // 2)).sum()


# ---------------- 2. Order flow ----------------
def delta(buy: pd.Series, sell: pd.Series) -> pd.Series:
    return buy - sell


def cvd(buy: pd.Series, sell: pd.Series) -> pd.Series:
    return (buy - sell).cumsum()


def trades_delta(trades: pd.DataFrame) -> dict:
    """Delta de trades agresores (en BTC y normalizado)."""
    buy = trades.loc[trades["side"] == "buy", "sz"].sum()
    sell = trades.loc[trades["side"] == "sell", "sz"].sum()
    tot = buy + sell
    return {"buy": buy, "sell": sell, "delta": buy - sell, "delta_ratio": (buy - sell) / tot if tot else np.nan}


def ofi(snapshots: list[dict]) -> float:
    """Order Flow Imbalance (Cont, Kukanov & Stoikov 2014) sobre el mejor nivel.

    e_t = 1{Pb_t >= Pb_{t-1}} qb_t - 1{Pb_t <= Pb_{t-1}} qb_{t-1}
        - 1{Pa_t <= Pa_{t-1}} qa_t + 1{Pa_t >= Pa_{t-1}} qa_{t-1}
    """
    total = 0.0
    for prev, cur in zip(snapshots, snapshots[1:]):
        pb0, qb0 = prev["bids"][0]
        pa0, qa0 = prev["asks"][0]
        pb1, qb1 = cur["bids"][0]
        pa1, qa1 = cur["asks"][0]
        e = (qb1 if pb1 >= pb0 else 0) - (qb0 if pb1 <= pb0 else 0)
        e += -(qa1 if pa1 <= pa0 else 0) + (qa0 if pa1 >= pa0 else 0)
        total += e
    return total


def _band(book: dict, band: float) -> tuple[float, float, float]:
    mid = (book["bids"][0][0] + book["asks"][0][0]) / 2
    bid = sum(p * q for p, q in book["bids"] if p >= mid * (1 - band))
    ask = sum(p * q for p, q in book["asks"] if p <= mid * (1 + band))
    return mid, bid, ask


def book_imbalance(book: dict, band: float = 0.005) -> float:
    """(bid - ask) / (bid + ask) en USD dentro de ±band del mid."""
    _, bid, ask = _band(book, band)
    return (bid - ask) / (bid + ask) if bid + ask else np.nan


def depth_usd(book: dict, band: float = 0.01) -> dict:
    _, bid, ask = _band(book, band)
    return {"bid_depth_usd": bid, "ask_depth_usd": ask, "depth_usd": bid + ask}


def spread_bps(book: dict) -> float:
    b, a = book["bids"][0][0], book["asks"][0][0]
    return (a - b) / ((a + b) / 2) * 1e4


# ---------------- 4. Liquidez ----------------
def amihud(close: pd.Series, quote_volume: pd.Series, n: int = 30) -> pd.Series:
    """Iliquidez de Amihud: media de |retorno| / volumen en USD (x1e9)."""
    illiq = close.pct_change().abs() / quote_volume.replace(0, np.nan) * 1e9
    return illiq.rolling(n, min_periods=max(2, n // 2)).mean()
