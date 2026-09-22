"""Los 7 bloques de señal. Cada módulo expone:

- ``daily(data) -> DataFrame``: componentes diarios en [-1, 1] y columna ``score``
  (vectorizado, sin look-ahead; se usa en el backtest y como base del modo live).
- ``live(data) -> BlockResult``: último valor diario + datos intradía/snapshot.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class BlockResult:
    name: str
    score: float                                   # [-1, 1]; >0 alcista, <0 bajista
    components: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.score is not None and math.isfinite(self.score)


def last_row(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return {}
    row = df.dropna(how="all").iloc[-1] if not df.dropna(how="all").empty else df.iloc[-1]
    return {k: float(v) for k, v in row.items() if pd.notna(v)}


from . import derivatives, liquidity, macro, onchain, orderflow, price, sentiment  # noqa: E402

BLOCKS = {
    "price": price,
    "orderflow": orderflow,
    "derivatives": derivatives,
    "liquidity": liquidity,
    "onchain": onchain,
    "macro": macro,
    "sentiment": sentiment,
}
