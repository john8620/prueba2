import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_data():
    """Datos sintéticos de las 7 fuentes (sin red)."""
    rng = np.random.default_rng(0)
    n = 900
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    close = 30000 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, n)))
    open_ = np.r_[close[0], close[:-1]]
    vol = rng.uniform(5000, 15000, n)
    candles = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                            "volume": vol, "quote_volume": vol * close}, index=idx)
    buy = rng.uniform(1e9, 2e9, n)
    sell = rng.uniform(1e9, 2e9, n)
    mvrv = 1.5 + 0.5 * np.sin(np.linspace(0, 6, n))
    mcap = close * 19.5e6
    onchain = pd.DataFrame({"mvrv": mvrv, "mcap": mcap, "realized_cap": mcap / mvrv,
                            "ex_inflow": rng.uniform(3e4, 5e4, n), "ex_outflow": rng.uniform(3e4, 5e4, n),
                            "ex_supply": 2.5e6 + np.cumsum(rng.normal(0, 1000, n))}, index=idx)
    onchain["ex_netflow"] = onchain["ex_inflow"] - onchain["ex_outflow"]
    macro = pd.DataFrame({"dxy": 120 + np.cumsum(rng.normal(0, 0.2, n)),
                          "nasdaq": 15000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
                          "us10y": 4 + np.cumsum(rng.normal(0, 0.02, n)),
                          "vix": 15 + np.abs(rng.normal(0, 5, n)),
                          "net_liquidity": 6000 + np.cumsum(rng.normal(0, 10, n))}, index=idx)
    return {
        "candles_d": candles,
        "taker_d": pd.DataFrame({"buy": buy, "sell": sell}, index=idx),
        "oi_d": pd.DataFrame({"oi_usd": 1e10 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))}, index=idx),
        "funding_d": pd.DataFrame({"funding": rng.normal(0.0003, 0.0002, n)}, index=idx),
        "ls_d": pd.DataFrame({"ls_ratio": rng.uniform(0.8, 1.5, n)}, index=idx),
        "onchain": onchain,
        "macro": macro,
        "stable": pd.Series(1.3e11 * np.exp(np.cumsum(rng.normal(0.0005, 0.002, n))), index=idx),
        "fng": pd.Series(rng.uniform(10, 90, n), index=idx),
        "_errors": {},
    }


@pytest.fixture
def book():
    return {"bids": [(100.0, 5.0), (99.9, 5.0), (99.0, 10.0)],
            "asks": [(100.1, 1.0), (100.2, 1.0), (101.5, 10.0)]}
