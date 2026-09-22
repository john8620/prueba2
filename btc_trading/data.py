"""Carga de datos de las 7 fuentes, tolerante a fallos (cada fuente es opcional)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pandas as pd

from .config import Config
from .sources import coinglass, liquidity, macro, onchain, sentiment
from .sources.binance import Binance
from .sources.okx import OKX


def exchange(cfg: Config):
    if cfg.exchange == "binance":
        return Binance(cfg.spot_inst.replace("-", ""))
    return OKX(cfg.spot_inst, cfg.swap_inst, cfg.symbol)


def to_daily(obj):
    """Normaliza el índice a días UTC (00:00) para alinear fuentes."""
    if obj is None or len(obj) == 0:
        return obj
    obj = obj.copy()
    obj.index = pd.DatetimeIndex(obj.index).tz_convert("UTC").normalize()
    return obj[~obj.index.duplicated(keep="last")]


def _run(tasks: dict[str, Callable], errors: dict) -> dict:
    out = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {k: pool.submit(fn) for k, fn in tasks.items()}
        for k, f in futs.items():
            try:
                out[k] = f.result()
            except Exception as exc:  # noqa: BLE001 - una fuente caída no detiene el sistema
                errors[k] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def load_daily(cfg: Config, days: int = 1500) -> dict:
    """Series diarias históricas (backtest y contexto del modo live)."""
    ex = exchange(cfg)
    start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days + 400)).strftime("%Y-%m-%d")
    errors: dict[str, str] = {}
    tasks = {
        "candles_d": lambda: ex.candles("1D", days),
        "taker_d": lambda: ex.taker_volume("1D"),
        "oi_d": lambda: ex.open_interest("1D"),
        "funding_raw": lambda: ex.funding_history(min(days * 3, 1500)),
        "ls_d": lambda: ex.long_short_ratio("1D"),
        "onchain": lambda: onchain.coinmetrics(start=start),
        "macro": lambda: macro.macro_frame(start=start),
        "stable": liquidity.stablecoin_mcap,
        "fng": lambda: sentiment.fear_greed(0),
    }
    key = cfg.coinglass_api_key
    if key:
        tasks.update({
            "cg_oi": lambda: coinglass.aggregated_oi(key),
            "cg_funding": lambda: coinglass.oi_weighted_funding(key),
            "liq_d": lambda: coinglass.aggregated_liquidations(key),
        })
    data = _run(tasks, errors)
    if data.get("funding_raw") is not None:
        data["funding_d"] = data.pop("funding_raw").resample("1D").sum(min_count=1)
    # CoinGlass (agregado multi-exchange) tiene prioridad si está disponible
    if data.get("cg_oi") is not None:
        data["oi_d"] = data.pop("cg_oi")
    if data.get("cg_funding") is not None:
        # CoinGlass da funding por intervalo de 8h en %; lo pasamos a tasa diaria decimal
        data["funding_d"] = data.pop("cg_funding") * 3 / 100
    for k in ["candles_d", "taker_d", "oi_d", "funding_d", "ls_d", "onchain", "stable", "fng", "liq_d"]:
        if data.get(k) is not None:
            data[k] = to_daily(data[k])
    if data.get("macro") is not None:
        data["macro"] = to_daily(data["macro"])
    data["_errors"] = errors
    return data


def load_live(cfg: Config, days: int = 800, book_snapshots: int = 5, snapshot_interval: float = 1.0) -> dict:
    """Datos diarios + intradía/snapshot para la señal en tiempo real."""
    data = load_daily(cfg, days)
    errors = data["_errors"]
    ex = exchange(cfg)

    def books():
        snaps = []
        for i in range(book_snapshots):
            snaps.append(ex.orderbook())
            if i < book_snapshots - 1:
                time.sleep(snapshot_interval)
        return snaps

    tasks = {
        "candles_h": lambda: ex.candles(cfg.bar, 24 * 30),
        "taker_h": lambda: ex.taker_volume("1H"),
        "ls_h": lambda: ex.long_short_ratio("1H"),
        "trades": lambda: ex.trades(500),
        "books": books,
        "liqs": lambda: ex.liquidations(100),
        "basis": ex.basis,
        "funding_now": ex.current_funding,
        "news": lambda: sentiment.news(24),
        "trending_rank": sentiment.coingecko_trending_rank,
        "mempool_fees": onchain.mempool_fees,
    }
    data.update(_run(tasks, errors))
    return data
