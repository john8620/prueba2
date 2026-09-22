import math

import numpy as np
import pandas as pd

from btc_trading.backtest import block_attribution, run_backtest
from btc_trading.blocks import BLOCKS
from btc_trading.blocks.sentiment import fg_component
from btc_trading.config import Config
from btc_trading.engine import daily_scores, decide, live_signal, trade_plan


def test_all_blocks_daily_in_range(synthetic_data):
    for name, mod in BLOCKS.items():
        d = mod.daily(synthetic_data)
        assert not d.empty, name
        s = d["score"].dropna()
        assert len(s) > 100, name
        assert s.between(-1, 1).all(), name


def test_no_lookahead(synthetic_data):
    """Modificar el futuro no debe cambiar las puntuaciones pasadas."""
    base = daily_scores(synthetic_data)
    mod = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in synthetic_data.items()}
    cut = mod["candles_d"].index[600]
    for k in ["candles_d", "onchain", "macro", "taker_d", "oi_d"]:
        mod[k].loc[mod[k].index > cut] *= 1.5
    mod["fng"].loc[mod["fng"].index > cut] = 99
    new = daily_scores(mod)
    cols = [c for c in BLOCKS if c in base]
    pd.testing.assert_frame_equal(base.loc[:cut, cols], new.loc[:cut, cols])


def test_live_signal_offline(synthetic_data, book):
    data = dict(synthetic_data, books=[book, book])
    sig = live_signal(data, Config())
    assert sig.direction in {"LONG", "SHORT", "FLAT"}
    assert math.isfinite(sig.composite) and -1 <= sig.composite <= 1
    assert 0 <= sig.confidence <= 1
    assert all(r.available for r in sig.blocks.values())


def test_missing_sources_degrade_gracefully(synthetic_data):
    data = {k: synthetic_data[k] for k in ["candles_d", "fng", "_errors"]}
    sig = live_signal(data, Config())
    assert math.isfinite(sig.composite)
    assert not sig.blocks["macro"].available


def test_trade_plan_risk():
    cfg = Config(equity=10_000, risk_per_trade=0.01, atr_stop_mult=2, max_leverage=10)
    p = trade_plan("LONG", 100_000, 2_000, cfg)
    assert p["stop_loss"] == 96_000
    assert abs(p["qty_btc"] * 4_000 - 100) < 1e-6      # pérdida al stop = 1% del capital
    p = trade_plan("SHORT", 100_000, 2_000, cfg)
    assert p["stop_loss"] > 100_000 and p["take_profit"] < 100_000


def test_leverage_cap():
    cfg = Config(equity=1_000, risk_per_trade=0.05, max_leverage=2)
    p = trade_plan("LONG", 100_000, 10, cfg)
    assert p["leverage"] <= 2


def test_decide_thresholds():
    cfg = Config()
    assert decide(0.5, cfg) == "LONG" and decide(-0.5, cfg) == "SHORT" and decide(0.0, cfg) == "FLAT"
    cfg.allow_short = False
    assert decide(-0.5, cfg) == "FLAT"


def test_fear_greed_contrarian():
    assert fg_component(10) > 0.5 and fg_component(90) < -0.5 and abs(fg_component(50)) < 1e-12


def test_backtest_runs(synthetic_data):
    scores = daily_scores(synthetic_data)
    res = run_backtest(scores, Config())
    assert len(res.equity) > 100
    assert np.isfinite(res.stats["max_drawdown"]) and res.stats["max_drawdown"] <= 0
    assert set(res.positions.unique()) <= {-1, 0, 1}
    ic = block_attribution(scores)
    assert "price" in ic.index
