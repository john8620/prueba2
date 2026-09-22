"""Backtest diario sin look-ahead.

La señal se calcula con datos hasta el cierre del día t y se ejecuta en el cierre
de t (posición vigente durante t+1). Stops por ATR comprobados con el high/low
diario. Comisiones + slippage por cada cambio de posición.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .engine import composite_series


@dataclass
class BacktestResult:
    equity: pd.Series
    benchmark: pd.Series
    positions: pd.Series
    composite: pd.Series
    trades: pd.DataFrame
    stats: dict


def _stats(rets: pd.Series, equity: pd.Series) -> dict:
    n = len(rets)
    years = n / 365
    total = equity.iloc[-1] - 1
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 and equity.iloc[-1] > 0 else float("nan")
    vol = rets.std() * math.sqrt(365)
    sharpe = rets.mean() / rets.std() * math.sqrt(365) if rets.std() > 0 else float("nan")
    downside = rets[rets < 0].std() * math.sqrt(365)
    sortino = rets.mean() * 365 / downside if downside > 0 else float("nan")
    dd = equity / equity.cummax() - 1
    return {"total_return": total, "cagr": cagr, "vol_ann": vol, "sharpe": sharpe,
            "sortino": sortino, "max_drawdown": dd.min(),
            "calmar": cagr / abs(dd.min()) if dd.min() < 0 else float("nan")}


def run_backtest(scores: pd.DataFrame, cfg: Config, fee: float = 0.0006,
                 exit_threshold: float = 0.0, start: str | None = None) -> BacktestResult:
    df = scores.dropna(subset=["close"]).copy()
    df["composite"] = composite_series(df, cfg)
    if start:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    df = df[df["composite"].notna()]
    if len(df) < 30:
        raise ValueError("Historial insuficiente para el backtest")

    pos, entry, stop, entry_ts = 0, None, None, None
    rets, positions, trades = [], [], []
    closes, lows, highs = df["close"].values, df["low"].values, df["high"].values
    comp, atrs = df["composite"].values, df["atr_14"].values
    for i in range(len(df)):
        r = 0.0
        if i > 0 and pos != 0:
            prev = closes[i - 1]
            hit = (pos > 0 and lows[i] <= stop) or (pos < 0 and highs[i] >= stop)
            if hit:
                r = pos * (stop / prev - 1) - fee
                trades.append({"entry_ts": entry_ts, "exit_ts": df.index[i], "side": pos,
                               "entry": entry, "exit": stop, "pnl": pos * (stop / entry - 1), "reason": "stop"})
                pos = 0
            else:
                r = pos * (closes[i] / prev - 1)
        # Decisión al cierre del día i
        c, px = comp[i], closes[i]
        target = pos
        if pos == 0:
            if c >= cfg.long_threshold:
                target = 1
            elif c <= cfg.short_threshold and cfg.allow_short:
                target = -1
        elif pos > 0 and c < exit_threshold:
            target = -1 if (c <= cfg.short_threshold and cfg.allow_short) else 0
        elif pos < 0 and c > -exit_threshold:
            target = 1 if c >= cfg.long_threshold else 0
        if target != pos:
            if pos != 0:
                trades.append({"entry_ts": entry_ts, "exit_ts": df.index[i], "side": pos,
                               "entry": entry, "exit": px, "pnl": pos * (px / entry - 1), "reason": "signal"})
            r -= fee * abs(target - pos)
            pos = target
            if pos != 0:
                entry, entry_ts = px, df.index[i]
                stop = px - pos * cfg.atr_stop_mult * atrs[i]
        rets.append(r)
        positions.append(pos)

    rets = pd.Series(rets, index=df.index)
    equity = (1 + rets).cumprod()
    bench = df["close"] / df["close"].iloc[0]
    tr = pd.DataFrame(trades)
    stats = _stats(rets, equity)
    bstats = _stats(bench.pct_change().fillna(0), bench)
    stats.update({
        "n_trades": len(tr),
        "win_rate": float((tr["pnl"] > 0).mean()) if len(tr) else float("nan"),
        "avg_trade": float(tr["pnl"].mean()) if len(tr) else float("nan"),
        "exposure": float((pd.Series(positions) != 0).mean()),
        "days": len(df), "start": str(df.index[0].date()), "end": str(df.index[-1].date()),
        "buy_hold_return": bstats["total_return"], "buy_hold_sharpe": bstats["sharpe"],
        "buy_hold_max_drawdown": bstats["max_drawdown"],
    })
    return BacktestResult(equity, bench, pd.Series(positions, index=df.index), df["composite"], tr, stats)


def block_attribution(scores: pd.DataFrame, horizon: int = 7) -> pd.DataFrame:
    """Poder predictivo de cada bloque: correlación (IC) con el retorno futuro."""
    fwd = scores["close"].pct_change(horizon).shift(-horizon)
    rows = {}
    for col in [c for c in scores.columns if c not in {"open", "high", "low", "close", "atr_14", "rv_ratio"}]:
        s = scores[col]
        ok = s.notna() & fwd.notna()
        if ok.sum() < 30:
            continue
        rows[col] = {"ic_spearman": s[ok].rank().corr(fwd[ok].rank()),
                     "hit_rate": float((np.sign(s[ok]) == np.sign(fwd[ok])).mean()), "n": int(ok.sum())}
    return pd.DataFrame(rows).T
