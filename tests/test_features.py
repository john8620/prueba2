import numpy as np
import pandas as pd

from btc_trading import features as f


def test_atr_constant_range():
    idx = pd.date_range("2024-01-01", periods=50, freq="D")
    df = pd.DataFrame({"high": 110.0, "low": 90.0, "close": 100.0}, index=idx)
    assert abs(f.atr(df, 14).iloc[-1] - 20) < 1e-9


def test_vwap_equals_price_when_flat():
    idx = pd.date_range("2024-01-01", periods=30, freq="h")
    df = pd.DataFrame({"high": 10.0, "low": 10.0, "close": 10.0, "volume": 3.0}, index=idx)
    assert f.rolling_vwap(df, 24).iloc[-1] == 10.0


def test_book_metrics(book):
    assert f.book_imbalance(book, 0.005) > 0          # más bids que asks cerca del mid
    assert abs(f.spread_bps(book) - 0.1 / 100.05 * 1e4) < 1e-9
    d = f.depth_usd(book, 0.01)
    assert d["depth_usd"] == d["bid_depth_usd"] + d["ask_depth_usd"]


def test_ofi_sign():
    s0 = {"bids": [(100, 1)], "asks": [(101, 1)]}
    s1 = {"bids": [(100, 3)], "asks": [(101, 1)]}   # crece la cola de bids -> OFI positivo
    s2 = {"bids": [(100, 3)], "asks": [(101, 4)]}   # crece la cola de asks -> OFI negativo
    assert f.ofi([s0, s1]) == 2
    assert f.ofi([s1, s2]) == -3


def test_trades_delta():
    t = pd.DataFrame({"sz": [1.0, 2.0, 1.0], "side": ["buy", "buy", "sell"]})
    d = f.trades_delta(t)
    assert d["delta"] == 2 and abs(d["delta_ratio"] - 0.5) < 1e-12


def test_combine_ignores_nan():
    assert f.combine({"a": (0.5, 1), "b": (float("nan"), 3)}) == 0.5
    assert np.isnan(f.combine({"a": (float("nan"), 1)}))


def test_amihud_positive():
    close = pd.Series(np.linspace(100, 120, 40))
    qv = pd.Series(1e9, index=close.index)
    assert (f.amihud(close, qv, 10).dropna() > 0).all()
