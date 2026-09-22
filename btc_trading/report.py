"""Formato de salida en consola."""
from __future__ import annotations

import math

from .engine import Signal

NAMES = {"price": "1. Precio", "orderflow": "2. Order Flow", "derivatives": "3. Derivados",
         "liquidity": "4. Liquidez", "onchain": "5. On-chain", "macro": "6. Macro", "sentiment": "7. Psicología"}


def bar(x: float, width: int = 20) -> str:
    if x is None or not math.isfinite(x):
        return " " * width + "│" + " " * width
    n = int(round(abs(x) * width))
    left = " " * (width - n) + "█" * n if x < 0 else " " * width
    right = "█" * n + " " * (width - n) if x > 0 else " " * width
    return left + "│" + right


def fmt(v) -> str:
    if isinstance(v, float):
        if not math.isfinite(v):
            return "n/d"
        if abs(v) >= 1e6:
            return f"{v:,.0f}"
        if abs(v) >= 100:
            return f"{v:,.2f}"
        return f"{v:.4g}"
    return str(v)


def render_signal(sig: Signal, verbose: bool = False) -> str:
    lines = [f"═══ BTC · Sistema de 7 bloques · {sig.timestamp:%Y-%m-%d %H:%M} UTC ═══", ""]
    lines.append(f"{'Bloque':<16}{'score':>7}   {'bajista':<20}│{'alcista':>20}")
    for k, r in sig.blocks.items():
        s = r.score
        lines.append(f"{NAMES[k]:<16}{fmt(s) if math.isfinite(s) else 'n/d':>7}   {bar(s)}")
        if verbose:
            for ck, cv in r.components.items():
                lines.append(f"    · {ck:<22}{fmt(cv):>8}   {bar(cv, 10)}")
    lines += ["", f"Compuesto: {sig.composite:+.3f} (bruto {sig.raw_composite:+.3f})   "
                  f"Confianza: {sig.confidence:.0%}   ➜  {sig.direction}", ""]
    for k, v in sig.plan.items():
        lines.append(f"  {k:<14} {fmt(v)}")
    key_metrics = [("price", "price"), ("price", "ret_24h"), ("price", "atr_14"), ("price", "rv_30d"),
                   ("price", "vwap_24h"), ("orderflow", "cvd_24h_usd"), ("orderflow", "book_imbalance_0.5pct"),
                   ("orderflow", "ofi"), ("derivatives", "oi_usd"), ("derivatives", "funding_now_8h"),
                   ("derivatives", "basis_annualized"), ("liquidity", "spread_bps"), ("liquidity", "depth_usd"),
                   ("liquidity", "stablecoin_mcap"), ("onchain", "mvrv"), ("onchain", "sopr"),
                   ("onchain", "realized_cap"), ("onchain", "ex_netflow_7d"), ("macro", "dxy"), ("macro", "vix"),
                   ("macro", "us10y"), ("macro", "net_liquidity_bn"), ("sentiment", "fear_greed"),
                   ("sentiment", "ls_ratio_now"), ("sentiment", "news_sentiment"), ("sentiment", "news_count_24h")]
    lines += ["", "Métricas clave:"]
    for blk, mk in key_metrics:
        v = sig.blocks[blk].metrics.get(mk)
        if v is not None:
            lines.append(f"  {blk + '.' + mk:<36} {fmt(v)}")
    if sig.notes:
        lines += ["", "Alertas:"] + [f"  ⚠ {n}" for n in sig.notes]
    if sig.errors:
        lines += ["", "Fuentes no disponibles (el sistema renormaliza pesos):"]
        lines += [f"  - {k}: {v}" for k, v in sig.errors.items()]
    lines += ["", "Aviso: herramienta de análisis; no es asesoramiento financiero."]
    return "\n".join(lines)


def render_backtest(stats: dict) -> str:
    pct = {"total_return", "cagr", "vol_ann", "max_drawdown", "win_rate", "avg_trade", "exposure",
           "buy_hold_return", "buy_hold_max_drawdown"}
    lines = ["═══ Backtest diario ═══"]
    for k, v in stats.items():
        lines.append(f"  {k:<24} {v:.2%}" if k in pct and isinstance(v, float) and math.isfinite(v)
                     else f"  {k:<24} {fmt(v)}")
    return "\n".join(lines)
