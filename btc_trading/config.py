"""Configuración central: pesos por bloque, umbrales, riesgo y claves opcionales."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Peso de cada bloque en la señal compuesta (se normalizan sobre los bloques disponibles).
DEFAULT_WEIGHTS: dict[str, float] = {
    "price": 0.20,
    "orderflow": 0.15,
    "derivatives": 0.20,
    "liquidity": 0.10,
    "onchain": 0.15,
    "macro": 0.10,
    "sentiment": 0.10,
}


@dataclass
class Config:
    symbol: str = "BTC"
    spot_inst: str = "BTC-USDT"
    swap_inst: str = "BTC-USDT-SWAP"
    bar: str = "1H"                 # timeframe intradía para precio/order flow
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    # Umbrales de la señal compuesta (rango [-1, 1])
    long_threshold: float = 0.20
    short_threshold: float = -0.20
    allow_short: bool = True

    # Gestión de riesgo
    equity: float = 10_000.0
    risk_per_trade: float = 0.01    # 1% del capital arriesgado por operación
    atr_stop_mult: float = 2.0
    atr_tp_mult: float = 3.0
    max_leverage: float = 3.0

    # Claves opcionales (si no existen, las fuentes correspondientes se omiten)
    coinglass_api_key: str | None = field(default_factory=lambda: os.getenv("COINGLASS_API_KEY"))
    fred_api_key: str | None = field(default_factory=lambda: os.getenv("FRED_API_KEY"))

    # Fuente de mercado: "okx" (por defecto, sin clave) o "binance"
    exchange: str = field(default_factory=lambda: os.getenv("BTC_EXCHANGE", "okx"))
    timeout: float = 20.0
