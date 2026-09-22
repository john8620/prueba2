"""CLI: python -m btc_trading {signal,backtest,watch}"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict

from .backtest import block_attribution, run_backtest
from .config import Config
from .data import load_daily, load_live
from .engine import daily_scores, live_signal
from .report import render_backtest, render_signal


def _clean(o):
    if isinstance(o, float):
        return None if not math.isfinite(o) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def cmd_signal(cfg: Config, args) -> None:
    sig = live_signal(load_live(cfg, book_snapshots=args.snapshots), cfg)
    if args.json:
        out = {"timestamp": str(sig.timestamp), "composite": sig.composite, "direction": sig.direction,
               "confidence": sig.confidence, "plan": sig.plan, "notes": sig.notes, "errors": sig.errors,
               "blocks": {k: asdict(v) for k, v in sig.blocks.items()}}
        print(json.dumps(_clean(out), indent=2, default=str))
    else:
        print(render_signal(sig, verbose=args.verbose))


def cmd_backtest(cfg: Config, args) -> None:
    data = load_daily(cfg, args.days)
    scores = daily_scores(data)
    res = run_backtest(scores, cfg, fee=args.fee, start=args.start)
    print(render_backtest(res.stats))
    print("\nPoder predictivo por bloque (IC Spearman vs retorno a 7 días):")
    print(block_attribution(scores).round(3).to_string())
    if data["_errors"]:
        print("\nFuentes no disponibles:", data["_errors"])
    if args.csv:
        out = scores.assign(composite=res.composite, position=res.positions, equity=res.equity)
        out.to_csv(args.csv)
        print(f"\nSeries guardadas en {args.csv}")


def cmd_watch(cfg: Config, args) -> None:
    while True:
        sig = live_signal(load_live(cfg, book_snapshots=args.snapshots), cfg)
        print(f"{sig.timestamp:%Y-%m-%d %H:%M} composite={sig.composite:+.3f} "
              f"conf={sig.confidence:.0%} -> {sig.direction} {sig.plan.get('entry', '')}", flush=True)
        time.sleep(args.interval)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="btc_trading", description="Sistema de trading BTC de 7 bloques")
    p.add_argument("--exchange", choices=["okx", "binance"], help="fuente de mercado (defecto: okx)")
    p.add_argument("--equity", type=float, help="capital para el cálculo del tamaño")
    p.add_argument("--risk", type=float, help="riesgo por operación (0.01 = 1%%)")
    p.add_argument("--long-only", action="store_true", help="desactiva cortos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("signal", help="señal actual con plan de trade")
    s.add_argument("--json", action="store_true")
    s.add_argument("-v", "--verbose", action="store_true", help="muestra sub-componentes")
    s.add_argument("--snapshots", type=int, default=5, help="snapshots del libro para OFI")

    b = sub.add_parser("backtest", help="backtest diario")
    b.add_argument("--days", type=int, default=1500)
    b.add_argument("--start", help="fecha inicio YYYY-MM-DD")
    b.add_argument("--fee", type=float, default=0.0006, help="comisión+slippage por lado")
    b.add_argument("--csv", help="guardar series diarias en CSV")

    w = sub.add_parser("watch", help="recalcula la señal periódicamente")
    w.add_argument("--interval", type=int, default=900, help="segundos entre cálculos")
    w.add_argument("--snapshots", type=int, default=5)

    args = p.parse_args(argv)
    cfg = Config()
    if args.exchange:
        cfg.exchange = args.exchange
    if args.equity:
        cfg.equity = args.equity
    if args.risk:
        cfg.risk_per_trade = args.risk
    if args.long_only:
        cfg.allow_short = False
    {"signal": cmd_signal, "backtest": cmd_backtest, "watch": cmd_watch}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
