# Sistema de trading de Bitcoin — 7 bloques

Sistema cuantitativo en Python que combina **7 bloques de métricas** en una señal
compuesta (LONG / SHORT / FLAT) con plan de trade (entrada, stop por ATR, take-profit
y tamaño por riesgo fijo), más un **backtest diario sin look-ahead**.

> ⚠️ Herramienta de análisis y paper trading. **No ejecuta órdenes** y no es
> asesoramiento financiero.

## Bloques, métricas y fuentes

| Bloque | Métricas | Fuente (gratis, sin clave salvo indicación) | Lógica |
|---|---|---|---|
| **1. Precio** | Return (1d/7d/30d/24h), ATR, RV (7/30/90d, 24h), VWAP (20d y 24h) | OKX velas (o Binance) | Tendencia vs EMA50 y VWAP medida en ATRs + momentum z-score. RV7/RV90 activa el filtro de régimen |
| **2. Order Flow** | CVD, Delta, OFI, Bid/Ask imbalance | OKX taker volume, trades, libro de órdenes | Delta/CVD agresor (z-score); OFI de Cont-Kukanov-Stoikov sobre N snapshots del libro; imbalance ±0,5% |
| **3. Derivados** | OI, Funding, Basis, Liquidaciones | OKX (OI, funding, mark/índice, futuro trimestral, liquidaciones) · **CoinGlass** agregado si hay clave | OI confirma la dirección del precio; funding y basis **contrarian** en extremos; cascadas de liquidaciones = capitulación |
| **4. Liquidez** | Depth ±1%, Spread, Amihud, Stablecoin liquidity | Libro OKX, velas, DefiLlama | Amihud al alza = bajista; crecimiento de stablecoins = alcista; depth/spread ajustan el tamaño (`quality`) |
| **5. On-chain** | Exchange flows (in/out/netflow, supply en exchanges), MVRV, SOPR, Realized cap | CoinMetrics Community, mempool.space | Netflow positivo = bajista; MVRV z-score contrarian; SOPR contrarian; crecimiento de realized cap = entrada de capital |
| **6. Macro** | DXY, Nasdaq, yields (10Y/2Y), VIX, liquidez global | FRED | Dólar, yields y VIX al alza = bajista; Nasdaq y **Fed net liquidity** (WALCL − TGA − RRP) al alza = alcista |
| **7. Psicología** | Fear & Greed, sentimiento de noticias, social volume, posicionamiento | alternative.me, RSS (Cointelegraph, Decrypt, Bitcoin Magazine), CoinGecko trending, long/short ratio OKX | F&G contrarian no lineal (fuerte solo en extremos), L/S ratio contrarian, léxico de titulares; la atención social amplifica el contrarian |

Notas sobre proxies:
- **DXY** → índice dólar amplio de la Fed (`DTWEXBGS`), gratuito y muy correlacionado.
- **Realized cap** = market cap / MVRV (CoinMetrics).
- **SOPR** no es gratuito: con `COINMETRICS_API_KEY` se usa el real; si no, un proxy de
  STH-SOPR = precio / VWAP de 155 días.
- **Liquidez global** → Fed net liquidity (se puede ampliar con balances BCE/BoJ).

## Cómo se combina

1. Cada métrica se normaliza (z-score rodante → `tanh`) a un componente en `[-1, 1]`.
2. Cada bloque es la media ponderada de sus componentes disponibles.
3. Señal compuesta = media ponderada de bloques (`config.DEFAULT_WEIGHTS`), renormalizada
   si falta alguna fuente.
4. **Filtro de régimen**: si RV7/RV90 > 1,5 la exposición se multiplica por 0,75 (0,5 si > 2).
5. `≥ +0,20` → LONG, `≤ −0,20` → SHORT, en medio → FLAT. En el backtest hay histéresis:
   se sale cuando el compuesto cruza 0 o salta el stop.
6. Plan: stop = 2×ATR(14d), TP = 3×ATR, tamaño = capital × 1% / distancia al stop,
   ajustado por confianza (acuerdo entre bloques), régimen y calidad de liquidez, con
   apalancamiento máximo 3×.

## Uso

```bash
pip install -r requirements.txt

python -m btc_trading signal            # señal actual + plan de trade
python -m btc_trading signal -v         # con sub-componentes de cada bloque
python -m btc_trading signal --json     # salida JSON (para bots/dashboards)
python -m btc_trading backtest --days 1500 --csv series.csv
python -m btc_trading watch --interval 900   # recalcula cada 15 min

# opciones globales
python -m btc_trading --exchange binance --equity 25000 --risk 0.005 --long-only signal
```

Variables de entorno opcionales:

| Variable | Efecto |
|---|---|
| `COINGLASS_API_KEY` | OI, funding ponderado por OI y liquidaciones **agregadas multi-exchange** (CoinGlass v4) |
| `COINMETRICS_API_KEY` | SOPR real y API Pro de CoinMetrics |
| `BTC_EXCHANGE=binance` | usa Binance en lugar de OKX (Binance bloquea algunas regiones con HTTP 451) |

## Backtest (datos reales, 2022-08 → 2026-09, comisión+slippage 0,06% por lado)

| | Sistema (long/short) | Buy & hold |
|---|---|---|
| Retorno total | +114% | +257% |
| CAGR | 20,4% | — |
| Sharpe | 0,69 | 0,89 |
| Max drawdown | −37,5% | −53,0% |
| Exposición | 51% | 100% |

Lecturas honestas:
- El sistema reduce el drawdown pero **no bate a buy & hold** en este periodo alcista con
  los pesos por defecto (no optimizados, para evitar sobreajuste).
- Las APIs gratuitas de OKX solo dan ~6 meses de OI/funding y ~2 meses de taker volume
  diario, así que en el backtest los bloques de **Order Flow y Derivados apenas
  participan**; con `COINGLASS_API_KEY` el histórico de derivados es mucho más largo.
- On-chain es el bloque con mayor IC (≈0,11 a 7 días). Usa `block_attribution` para
  recalibrar pesos con validación walk-forward antes de operar con dinero real.

## Estructura

```
btc_trading/
  config.py        pesos, umbrales, riesgo, claves
  sources/         okx, binance, coinglass, onchain (CoinMetrics/mempool), macro (FRED),
                   liquidity (DefiLlama), sentiment (F&G, RSS, CoinGecko), http (reintentos+caché)
  features.py      ATR, RV, VWAP, CVD, OFI, imbalance, depth, spread, Amihud, z-scores
  blocks/          price, orderflow, derivatives, liquidity, onchain, macro, sentiment
  engine.py        señal compuesta, filtro de régimen, plan de trade
  backtest.py      backtest diario con stops ATR + atribución por bloque (IC)
  report.py        salida en consola
tests/             tests offline con datos sintéticos (incluye test de no look-ahead)
```

Tests: `python -m pytest -q`
