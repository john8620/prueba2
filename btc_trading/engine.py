"""Motor de señal: combina los 7 bloques, aplica filtros de régimen y genera el plan de trade."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .blocks import BLOCKS, BlockResult
from .config import Config
from .features import combine_frame


@dataclass
class Signal:
    timestamp: pd.Timestamp
    composite: float
    raw_composite: float
    direction: str                      # LONG / SHORT / FLAT
    confidence: float                   # 0-1: acuerdo entre bloques
    blocks: dict[str, BlockResult]
    plan: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def regime_multiplier(rv_ratio: float | None) -> float:
    """Reduce la exposición cuando la volatilidad se expande bruscamente."""
    if rv_ratio is None or not math.isfinite(rv_ratio):
        return 1.0
    if rv_ratio > 2.0:
        return 0.5
    if rv_ratio > 1.5:
        return 0.75
    return 1.0


def composite_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    num = den = 0.0
    for k, s in scores.items():
        if s is None or not math.isfinite(s):
            continue
        num += s * weights.get(k, 0)
        den += weights.get(k, 0)
    return num / den if den else float("nan")


def agreement(scores: dict[str, float], weights: dict[str, float], sign: float) -> float:
    valid = {k: s for k, s in scores.items() if s is not None and math.isfinite(s)}
    if not valid or sign == 0:
        return 0.0
    tot = sum(weights.get(k, 0) for k in valid)
    agree = sum(weights.get(k, 0) for k, s in valid.items() if np.sign(s) == np.sign(sign))
    return agree / tot if tot else 0.0


def decide(composite: float, cfg: Config) -> str:
    if not math.isfinite(composite):
        return "FLAT"
    if composite >= cfg.long_threshold:
        return "LONG"
    if composite <= cfg.short_threshold and cfg.allow_short:
        return "SHORT"
    return "FLAT"


def trade_plan(direction: str, price: float, atr_value: float, cfg: Config,
               size_mult: float = 1.0) -> dict:
    """Stop por ATR y tamaño por riesgo fijo (equity * risk / distancia al stop)."""
    if direction == "FLAT" or not (price and atr_value and math.isfinite(atr_value)):
        return {"action": "Sin posición / cerrar posiciones abiertas"}
    sgn = 1 if direction == "LONG" else -1
    stop = price - sgn * cfg.atr_stop_mult * atr_value
    tp = price + sgn * cfg.atr_tp_mult * atr_value
    risk_usd = cfg.equity * cfg.risk_per_trade * size_mult
    qty = risk_usd / abs(price - stop)
    notional = min(qty * price, cfg.equity * cfg.max_leverage)
    qty = notional / price
    return {
        "action": f"{'Comprar' if sgn > 0 else 'Vender en corto'} BTC",
        "entry": round(price, 2), "stop_loss": round(stop, 2), "take_profit": round(tp, 2),
        "risk_reward": round(cfg.atr_tp_mult / cfg.atr_stop_mult, 2),
        "qty_btc": round(qty, 6), "notional_usd": round(notional, 2),
        "leverage": round(notional / cfg.equity, 2), "risk_usd": round(risk_usd, 2),
    }


def live_signal(data: dict, cfg: Config) -> Signal:
    results = {name: mod.live(data) for name, mod in BLOCKS.items()}
    scores = {k: r.score for k, r in results.items()}
    raw = composite_score(scores, cfg.weights)
    rv_ratio = results["price"].metrics.get("rv_ratio")
    mult = regime_multiplier(rv_ratio)
    comp = raw * mult if math.isfinite(raw) else raw
    direction = decide(comp, cfg)
    conf = agreement(scores, cfg.weights, comp)
    pm = results["price"].metrics
    price = pm.get("price") or (data.get("candles_d")["close"].iloc[-1] if data.get("candles_d") is not None else None)
    quality = results["liquidity"].metrics.get("quality", 1.0)
    plan = trade_plan(direction, price, pm.get("atr_14"), cfg, size_mult=mult * quality * max(conf, 0.5))
    notes = [n for r in results.values() for n in r.notes]
    if mult < 1:
        notes.append(f"Filtro de régimen: exposición x{mult} por expansión de volatilidad.")
    ts = pd.Timestamp.now(tz="UTC")
    return Signal(ts, comp, raw, direction, conf, results, plan, notes, data.get("_errors", {}))


def daily_scores(data: dict) -> pd.DataFrame:
    """Puntuación diaria de cada bloque (para backtest/análisis)."""
    frames = {}
    for name, mod in BLOCKS.items():
        d = mod.daily(data)
        if not d.empty and "score" in d:
            frames[name] = d["score"]
    df = pd.DataFrame(frames)
    if data.get("candles_d") is not None:
        c = data["candles_d"]
        df = df.reindex(c.index)
        price = BLOCKS["price"].daily(data)
        df["rv_ratio"] = price["rv_ratio"]
        df["atr_14"] = price["atr_14"]
        df[["open", "high", "low", "close"]] = c[["open", "high", "low", "close"]]
    return df


def composite_series(scores: pd.DataFrame, cfg: Config) -> pd.Series:
    comp = combine_frame(scores, cfg.weights)
    mult = scores.get("rv_ratio", pd.Series(1.0, index=scores.index)).map(regime_multiplier)
    return comp * mult
