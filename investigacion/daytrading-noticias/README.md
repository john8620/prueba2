# Day trading de acciones basado en noticias en tiempo real

**Investigación: estrategias, evidencia, APIs gratuitas y repositorios de GitHub**
Fecha de corte: 30 de septiembre de 2026. Mercado principal analizado: acciones de EE. UU.

> **Aviso.** Esto es material de investigación y no una recomendación de inversión. El day trading
> tiene tasas de pérdida muy altas entre minoristas: en Brasil, el 97 % de quienes hicieron day
> trading más de 300 días perdió dinero ([Chague, De-Losso y Giovannetti](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)).
> Todo lo que sigue debe probarse primero en *paper trading*.

## Contenido

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Qué dice la evidencia sobre noticias y precios](#2-qué-dice-la-evidencia-sobre-noticias-y-precios)
3. [Catálogo de estrategias](#3-catálogo-de-estrategias)
4. [APIs y fuentes gratuitas](#4-apis-y-fuentes-gratuitas)
5. [Repositorios de GitHub](#5-repositorios-de-github)
6. [Arquitectura recomendada](#6-arquitectura-recomendada)
7. [Código de ejemplo](#7-código-de-ejemplo)
8. [Backtesting sin engañarse](#8-backtesting-sin-engañarse)
9. [Regulación y aspectos prácticos en 2026](#9-regulación-y-aspectos-prácticos-en-2026)
10. [Plan de acción sugerido](#10-plan-de-acción-sugerido)
11. [Fuentes](#11-fuentes)

---

## 1. Resumen ejecutivo

- **La velocidad pura no es la ventaja del minorista.** Los precios reaccionan en segundos a una
  noticia y los algoritmos con feeds de pago (Dow Jones, Bloomberg, Benzinga Pro) capturan el
  primer movimiento. La ventaja realista está en *qué* se opera (acciones "en juego" con volumen
  anormal), *cómo* se ejecuta (reglas simples y disciplinadas en los minutos u horas siguientes) y
  en filtrar el ruido.
- **La evidencia más útil para intradía:**
  - Operar un *Opening Range Breakout* (ORB) de 5 minutos solo en **"Stocks in Play"** (acciones con
    volumen relativo alto, casi siempre por noticias) dio +1.637 % neto y Sharpe 2,81 en 2016-2023
    frente al 29 % y Sharpe 0,48 del mismo ORB sobre todo el mercado
    ([Zarattini, Barbon y Aziz, 2024](https://ideas.repec.org/p/chf/rpseri/rp2498.html)).
  - Tras noticias hay **deriva** (sobre todo después de malas noticias) y tras grandes movimientos
    **sin** noticia hay **reversión** ([Chan, 2003](https://ideas.repec.org/a/eee/jfinec/v70y2003i2p223-260.html)).
  - Los LLM clasifican titulares con poder predictivo, más fuerte en *small caps* y noticias
    negativas, pero ese alfa **decae** a medida que más gente usa LLM
    ([Lopez-Lira y Tang](https://arxiv.org/abs/2304.07619)); la predictibilidad cae fuerte en los
    primeros dos días y dura más en empresas pequeñas ([Chen, Kelly y Xiu](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687)).
- **Stack con costo cero para empezar:** Alpaca (noticias Benzinga en tiempo real por WebSocket,
  históricas desde 2015, datos IEX y *paper trading*), fuentes primarias sin clave (SEC EDGAR, halts
  de Nasdaq, RSS de GlobeNewswire / Business Wire / PR Newswire), Finnhub (noticias por empresa,
  calendario de resultados, WebSocket de trades) y FinBERT local para sentimiento. El primer gasto
  que suele valer la pena es datos consolidados (SIP) para medir volumen relativo de todo el mercado.
- **Cambios de 2026 que importan:** la SEC aprobó eliminar la regla *Pattern Day Trader* de
  US$25.000 (vigente desde el 4 de junio de 2026; los brokers tienen hasta el 20 de octubre de 2027
  para aplicarla); Nasdaq y NYSE planean pasar a 23 horas diarias desde el 6 de diciembre de 2026;
  Polygon.io ahora se llama Massive; Reddit exige aprobación manual para su API, StockTwits cerró
  registros y X cobra por uso.
- **Incluido en este directorio:** un monitor de noticias gratuito y probado en vivo
  ([`ejemplos/monitor_noticias_gratis.py`](ejemplos/monitor_noticias_gratis.py)) y fragmentos para
  noticias en tiempo real, filtros de mercado, órdenes *bracket* y clasificación con LLM.

---

## 2. Qué dice la evidencia sobre noticias y precios

El ciclo de una noticia tiene dos fases. En la **primera (segundos)** compiten algoritmos con feeds
legibles por máquina. En la **segunda (minutos a días)** entran la atención de los minoristas, la
liquidez y la sub o sobre-reacción. El minorista solo puede competir en la segunda.

| Hallazgo | Fuente | Implicación práctica |
|---|---|---|
| Los precios reaccionan en segundos a menciones en CNBC; lo positivo se incorpora en ~1 minuto y lo negativo en ~15 minutos; solo quien ejecuta en ≤15 s gana algo, y poco | [Busse y Green, 2002](https://www.sciencedirect.com/science/article/abs/pii/S0304405X02001484) | No competir por latencia en acciones grandes |
| Cuando Dow Jones difunde un Form 4 (compras de insiders), el volumen salta en los 2 minutos siguientes aunque el dato ya era público en EDGAR | [Rogers, Skinner y Zechman, 2016](https://link.springer.com/article/10.1007/s11142-016-9354-2) | La difusión mueve el precio: la fuente primaria (EDGAR) puede adelantarse a los medios |
| Deriva tras noticias (más fuerte con malas noticias) y reversión tras movimientos extremos sin noticias | [Chan, 2003](https://ideas.repec.org/a/eee/jfinec/v70y2003i2p223-260.html) | Distinguir movimiento con catalizador (seguir) de movimiento sin catalizador (posible reversión) |
| El volumen anormalmente alto predice retornos positivos posteriores (efecto visibilidad) | [Gervais, Kaniel y Mingelgrin, 2001](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=146468) | El volumen relativo (RVOL) es el filtro central |
| Los minoristas son compradores netos de acciones que llaman la atención: en noticias, con volumen anormal o con retornos extremos | [Barber y Odean, 2008](https://academic.oup.com/rfs/article-abstract/21/2/785/1607197) | Explica el *momentum* de small caps con noticia y también sus reversiones |
| ORB de 5 minutos en top 20 Stocks in Play: +1.637 %, Sharpe 2,81, alfa 36 % anual, beta ≈ 0 (2016-2023, neto de comisiones) | [Zarattini, Barbon y Aziz, 2024](https://ideas.repec.org/p/chf/rpseri/rp2498.html) | La estrategia más documentada para intradía con noticias |
| GPT-4 predice la reacción inicial (~90 % de acierto, no operable) y parte de la deriva posterior, sobre todo en small caps y malas noticias; los retornos bajan al subir la adopción de LLM | [Lopez-Lira y Tang](https://arxiv.org/abs/2304.07619) | Un LLM sirve para clasificar y priorizar, no es una máquina de dinero |
| Embeddings de LLM sobre noticias predicen retornos; la predictibilidad cae fuerte en 2 días, dura más en small caps (16 mercados, 13 idiomas) | [Chen, Kelly y Xiu](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687) | Horizonte útil: intradía a pocos días |
| La deriva post-resultados (PEAD) sigue existiendo pero es más débil y se concentra en acciones difíciles de arbitrar | [Revisión en ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2214635020303750), [Quantpedia](https://quantpedia.com/strategies/post-earnings-announcement-effect) | En resultados, seguir el gap solo con confirmación de volumen |
| Al backtestear con LLM hay sesgo de anticipación (el modelo "conoce el futuro") y un efecto distracción por conocer la empresa | [Glasserman y Lin, 2023](https://arxiv.org/abs/2309.17322); [He et al. (ChronoBERT/ChronoGPT)](https://arxiv.org/abs/2502.21206) | Usar modelos *point-in-time* o anonimizar titulares al validar |

**Conclusión práctica:** hay ventaja cuando se combinan (1) un catalizador real y nuevo, (2) volumen
relativo alto que confirma que el mercado lo está tomando en serio, (3) una regla de entrada que no
requiera ser el primero, y (4) gestión de riesgo estricta.

---

## 3. Catálogo de estrategias

Cada estrategia indica catalizador, filtros, entrada, salida y riesgos. Los umbrales son puntos de
partida para backtestear, no valores óptimos.

### 3.1 ORB de 5 minutos en "Stocks in Play" (la más documentada)

Reglas del paper de [Zarattini, Barbon y Aziz (2024)](https://ideas.repec.org/p/chf/rpseri/rp2498.html):

| Paso | Regla |
|---|---|
| Universo | Precio de apertura > US$5; volumen medio de 14 días ≥ 1.000.000; ATR de 14 días > US$0,50 |
| "In play" | RVOL de los primeros 5 minutos (volumen 9:30-9:35 dividido por el promedio de esa misma ventana en los 14 días previos) ≥ 1,0, y solo las **20 con mayor RVOL** |
| Dirección | Vela de 5 minutos alcista: orden stop de compra en el máximo. Bajista: orden stop de venta en corto en el mínimo. Doji: no operar |
| Stop | 10 % del ATR de 14 días desde el precio de entrada |
| Salida | Sin objetivo: cierre a las 16:00 ET si no saltó el stop |
| Tamaño | Arriesgar 1 % del capital por posición; apalancamiento máximo 4x |
| Costos modelados | US$0,0035 por acción (comisión de IBKR Pro); **no** modela slippage explícito |
| Resultado 2016-2023 | +1.637 % neto, TIR 41,6 %, volatilidad 14,8 %, Sharpe 2,81, acierto 48,4 %, *drawdown* máximo 12 % (S&P 500: +198 %, Sharpe 0,78, *drawdown* 34 %) |

Cautelas: menos de la mitad de los días son positivos, así que el resultado depende de pocas
ganancias grandes; las órdenes stop en la apertura sufren slippage; y el resultado depende de los
parámetros y del período (la réplica pública en
[QuantConnect](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/)
es un buen punto de partida para comprobarlo) y el RVOL debe calcularse con volumen consolidado,
no solo el de un mercado.

### 3.2 Momentum de catalizador en small caps ("Gap and Go")

La estrategia típica del day trader minorista de momentum. Criterios populares ("5 pilares" de
Ross Cameron, [Warrior Trading](https://www.warriortrading.com/finding-stocks-to-day-trade/),
resumidos en un [script de TradingView](https://www.tradingview.com/script/mbqMf3pF-Ross-Cameron-5-Pillars-Filter/)):

- Sube ≥ 10 % en el día, con **noticia nueva** (resultados, contrato, FDA, alianza, etc.).
- RVOL ≥ 5x, precio entre US$1-2 y US$20, *float* < 20 millones de acciones (idealmente < 10 M).

Entrada habitual: ruptura del máximo del pre-market o primer retroceso ("bandera") que respeta el
VWAP, en velas de 1-5 minutos. Salida: stop bajo el mínimo del retroceso o si pierde el VWAP, toma
parcial en 2R, stop de tiempo.

Riesgos específicos: spreads amplios, pausas LULD, **ofertas de acciones el mismo día** (la
dilución suele hundir el precio), *pump and dumps*, restricción de ventas en corto (SSR) y
slippage. Es automatizable en la parte de escaneo y alertas; la ejecución suele ser manual o
semiautomática.

### 3.3 Resultados trimestrales (earnings)

- **Continuación del gap:** si la sorpresa en BPA (beneficio por acción), ingresos y *guidance* apuntan en la misma dirección
  y el RVOL es alto, operar a favor del gap con ORB o recuperación del VWAP tras la apertura.
- **Desvanecimiento (fade):** gap contra resistencia con noticia mixta (p. ej., supera BPA pero
  recorta *guidance*) y volumen que se agota.
- **Deriva post-resultados (PEAD):** efecto de varios días, hoy más débil; más útil como filtro
  (no operar contra una sorpresa grande) que como estrategia intradía.
- Fuentes gratis: calendario de Finnhub, `EARNINGS_CALENDAR` de Alpha Vantage, 8-K ítem 2.02 en
  EDGAR y los comunicados en los RSS de wires.

### 3.4 Halts: noticia pendiente (T1) y pausas por volatilidad (LULD)

- **T1 (noticia pendiente):** la empresa va a publicar algo material; la negociación reabre tras
  la noticia (código T3). Regla básica: **leer la noticia antes de operar la reapertura**, dejar
  pasar el primer minuto y operar a favor de la dirección confirmada por volumen.
- **LUDP (pausa LULD de 5 minutos):** tras un movimiento brusco. En tendencias fuertes suele
  reanudar en la misma dirección, pero con enorme volatilidad; tamaño reducido.
- Fuente gratuita: el [RSS de halts de Nasdaq](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltRSS)
  (máximo una consulta por minuto), incluido en el monitor de ejemplo. Códigos en
  [TradeHaltCodes](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes).

### 3.5 Eventos corporativos específicos

| Evento | Dónde detectarlo gratis | Reacción típica | Notas |
|---|---|---|---|
| Oferta de acciones / dilución (S-1, S-3, 424B5, *registered direct*, "pricing of offering") | EDGAR, RSS de wires | Caída de 20-30 % en promedio en small caps según [DilutionTracker](https://knowledge.dilutiontracker.com/en/articles/5722415-offerings-investment-bank-tiers-and-why-it-matters-for-small-cap-stocks); se colocan con descuento ([TradingSim](https://www.tradingsim.com/blog/stock-dilution-and-offerings-explained-for-beginners-tradingsim)) | Muchas se anuncian a última hora o fuera de horario; operar en corto exige *locate* y puede activar SSR |
| FDA / datos de ensayos clínicos | GlobeNewswire (feed "Clinical Study"), comunicados de la FDA | Binaria, gaps enormes | Tamaño pequeño; frecuentes halts |
| Fusión o adquisición (empresa objetivo) | 8-K ítem 1.01, feed de M&A de GlobeNewswire | Salto hacia el precio de la oferta y luego rango estrecho | Poco recorrido intradía después del gap; el comprador puede caer |
| Contratos y alianzas (gobierno, IA, cripto…) | RSS de wires | Picos en small caps que a menudo se desvanecen | Comparar el monto con la capitalización |
| *Guidance* o pre-anuncios | Wires, 8-K 2.02 / 7.01 | Gaps | Revisar si cambia el año completo |
| Cambios de recomendación de analistas | API de IBKR (Briefing.com Analyst Actions, gratis) | Movimiento moderado en grandes | Más útil en *large caps* |
| Compras de insiders (Form 4) | EDGAR | Reacción en minutos tras la difusión en medios | Mejor señal a días que intradía |
| Quiebra, aviso de exclusión, *reverse split* | 8-K 1.03, 3.01; wires | Bajista | Cuidado con *squeezes* |
| Incidente de ciberseguridad | 8-K ítem 1.05 | Bajista | Ítem obligatorio desde diciembre de 2023 |

### 3.6 Noticias macro (IPC, empleo, FOMC)

- Operar ETFs de índice (SPY, QQQ, IWM) o sectoriales sensibles (bancos, inmobiliarias, tecnología).
- Reglas de protección habituales: no abrir posiciones desde unos minutos antes hasta 10-15 minutos
  después del dato (30 minutos en el FOMC); esperar al cierre de la primera vela de 5-15 minutos y
  operar la ruptura de ese rango; el dato de empleo (NFP) es conocido por sus latigazos
  ([Benzinga](https://www.benzinga.com/Opinion/26/06/53097073/trading-systems-and-market-news-how-to-handle-cpi-fomc-and-unexpected-events),
  [FXEmpire](https://www.fxempire.com/education/article/news-driven-fx-trading-how-to-trade-events-like-the-fomc-cpi-and-nfp-1549791)).
- Fuentes gratis: RSS de comunicados de la Reserva Federal, calendario semanal en JSON de
  ForexFactory (no oficial) y el calendario del BLS.

### 3.7 Puntuación de sentimiento con NLP o LLM

- Puntuar cada titular (FinBERT gratis y local; un LLM de pago para los casos dudosos), ordenar y
  operar solo los extremos que además pasan filtros de precio, RVOL y gap.
- Úsalo como **filtro o priorizador**, no como señal única: el alfa publicado decae y los
  backtests con LLM tienen sesgo de anticipación (ver sección 8).
- Tutorial práctico: [análisis de sentimiento con la News API de Alpaca y transformers](https://alpaca.markets/learn/sentiment-analysis-with-news-api-and-transformers).

### 3.8 Atención en redes sociales

Los picos de menciones anticipan atención minorista (y por lo tanto *momentum* seguido de
reversión, en línea con Barber y Odean). En 2026 los datos sociales gratuitos son escasos: la API
de Reddit exige aprobación manual, StockTwits tiene los registros cerrados y X cobra por lectura
(ver sección 4.4).

### 3.9 Reversión de movimientos sin catalizador

Siguiendo a Chan (2003): un movimiento extremo **sin** noticia identificable es candidato a
reversión; un movimiento **con** noticia fuerte no se debe desvanecer a ciegas. El monitor de
noticias sirve aquí como filtro negativo.

---

## 4. APIs y fuentes gratuitas

Condiciones revisadas en septiembre de 2026; los planes cambian a menudo, así que conviene
confirmarlas antes de construir sobre ellas.

### 4.1 APIs de noticias financieras (planes gratuitos)

| Proveedor | Qué da gratis | Límites del plan gratis | Tiempo real | Comentario |
|---|---|---|---|---|
| **[Alpaca News API](https://docs.alpaca.markets/us/docs/streaming-real-time-news)** | Noticias de Benzinga: REST histórico desde 2015 y WebSocket `wss://stream.data.alpaca.markets/v1beta1/news` | 200 llamadas/min en el plan gratuito; requiere claves de API (una cuenta de *paper trading* basta) | Sí (WebSocket) | La mejor opción gratuita: 600-900 titulares diarios. Se lanzó como beta sin costo y Alpaca avisó que el precio podría cambiar ([anuncio](https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/)); confírmalo al abrir la cuenta |
| **[Finnhub](https://finnhub.io/docs/api/market-news)** | `company-news` (empresas de Norteamérica, 1 año de historia), noticias generales y de fusiones, calendario de resultados e IPO | 60 llamadas/min | Por sondeo REST; el WebSocket de noticias y `news-sentiment` son de pago | WebSocket de **trades** gratis para 50 símbolos de EE. UU. |
| **[Massive](https://massive.com/pricing)** (ex Polygon.io) | Plan Stocks Basic | 5 llamadas/min, solo datos de fin de día, 2 años | No (tiempo real desde US$199/mes) | Polygon.io pasó a llamarse Massive el 30-oct-2025 ([anuncio](https://massive.com/blog/polygon-is-now-massive)); `api.polygon.io` sigue funcionando |
| **[Alpha Vantage](https://www.alphavantage.co/premium/)** | `NEWS_SENTIMENT` con sentimiento por ticker | 25 peticiones/día | No | Útil para pruebas, no para intradía |
| **[Marketaux](https://www.marketaux.com/pricing)** | Noticias con entidades y sentimiento | 100 peticiones/día, 3 artículos por petición | Por sondeo | Planes desde US$29/mes |
| **[EODHD](https://eodhd.com/financial-apis/stock-market-financial-news-api)** | Noticias con sentimiento | 20 llamadas/día; cada petición de noticias cuesta 5 (≈4 al día) | No (15-60 min de retraso) | Para investigación, no para ejecución |
| **[TickerTick](https://github.com/hczhu/TickerTick-API)** | Agregador de noticias por ticker con tipos (`T:sec`, `T:earning`, `T:curated`…) | Sin clave; 10 peticiones/min por IP | Por sondeo (latencia no documentada) | Uso comercial y no comercial permitido |
| **[GDELT DOC 2.0](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)** | Noticias globales en más de 100 idiomas, con tono | Sin clave; 1 petición cada 5 s | Actualiza cada 15 min | Macro y geopolítica |
| **[API de Interactive Brokers](https://interactivebrokers.github.io/tws-api/news.html)** | Briefing.com General Market Columns (BRFG), Briefing.com Analyst Actions (BRFUPDN), Dow Jones Newsletters (DJNL) | Requiere cuenta en IBKR | Sí | Benzinga y otras fuentes vía IB son de pago |
| **[sec-api.io](https://sec-api.io/)** | WebSocket de nuevos *filings* (~300 ms tras publicarse) | 100 llamadas gratis en total | Sí | Luego de pago |
| **[Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs)** | Endpoints de noticias y comunicados | 250 llamadas/día | Depende del plan | Confirmar qué endpoints de noticias incluye el plan gratis |
| **[NewsAPI.org](https://newsapi.org/pricing)** | Noticias generales | 100 peticiones/día, **24 h de retraso**, solo desarrollo | No | No sirve para trading |
| **[Tiingo News](https://www.tiingo.com/about/pricing)** | — | No incluida en el plan gratis | — | Plan Power (US$30/mes) |
| **Benzinga directo** | — | API solo con prueba por solicitud; la plataforma Benzinga Pro ronda US$197/mes tras 14 días de prueba | — | Sus noticias llegan gratis vía Alpaca |

Servicios web útiles con plan gratuito: [Stock Titan](https://www.stocktitan.net/pricing) (noticias
y *filings* con 1 minuto de retraso gratis; tiempo real desde US$59,99/mes) y
[rtpr.io](https://rtpr.io/) (comunicados con 5 minutos de retraso gratis; afirma ~190 ms en su plan
Pro de US$139/mes y 3-10 minutos para los feeds gratuitos, dato del propio proveedor).

### 4.2 Fuentes primarias sin clave (probadas el 30-sep-2026)

| Fuente | URL | Qué trae | Reglas de uso |
|---|---|---|---|
| Últimos 8-K de EDGAR (Atom) | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=40&output=atom` | Empresa, CIK y **lista de ítems** (1.01, 2.02, 3.02…), así que se clasifica sin descargar el documento | Máximo 10 peticiones/s y encabezado `User-Agent` con nombre y correo ([reglas de la SEC](https://www.sec.gov/about/developer-resources)) |
| API de EDGAR | `https://data.sec.gov/submissions/CIK##########.json` | Historial de *filings* por empresa, con demora típica menor a 1 s ([documentación](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)) | Igual que arriba |
| Mapa CIK ↔ ticker | `https://www.sec.gov/files/company_tickers.json` | ~10.000 tickers | Igual que arriba |
| Halts de Nasdaq (RSS) | `https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts` | Símbolo, código (T1, LUDP…), hora del halt y de reanudación | Máximo 1 consulta por minuto |
| GlobeNewswire (RSS) | [lista de feeds](https://www.globenewswire.com/rss/list) | Comunicados; los **tickers vienen en `<category>`** (p. ej. `NASDAQ:XXXX`) | Feeds por tema: resultados, M&A, ensayos clínicos… |
| Business Wire (RSS) | `https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJcFVJYWQ==` | Todo el wire de ~7 días; tickers como *cashtags* (`$XXXX`) | Feeds personalizables ([opciones](https://www.businesswire.com/help/feed-options)) |
| PR Newswire (RSS) | `https://www.prnewswire.com/rss/all-news-releases-list.rss` | Últimos 20 comunicados; tickers en el texto (`(NASDAQ: XXXX)`) | La URL `news-releases-list.rss` redirige a veces a una página 404 |
| Reserva Federal (RSS) | `https://www.federalreserve.gov/feeds/press_all.xml` | Comunicados del FOMC y otros | — |
| Calendario macro (no oficial) | `https://nfs.faireconomy.media/ff_calendar_thisweek.json` | Eventos de la semana con impacto y previsión | Uso razonable |

Hallazgo práctico: una gran parte de los titulares con ticker en los wires son **avisos de
bufetes de abogados** buscando demandantes ("Investors Have Opportunity to Lead…", "Robbins LLP
Urges…"). No aportan información nueva y conviene filtrarlos; el monitor de ejemplo lo hace.

### 4.3 Datos de mercado en tiempo real (para confirmar con precio y volumen)

| Opción | Costo | Qué da | Limitación clave |
|---|---|---|---|
| [Alpaca Basic](https://docs.alpaca.markets/docs/about-market-data-api) | Gratis | Tiempo real de **IEX**, WebSocket de 30 símbolos, históricos desde 2016, 200 llamadas/min | IEX es un solo mercado: ve una fracción del volumen, y los datos consolidados recientes (últimos 15 min) no están disponibles |
| Alpaca Algo Trader Plus | US$99/mes | Todos los mercados de EE. UU. (SIP), símbolos ilimitados | — |
| Finnhub (plan gratis) | Gratis | WebSocket de trades de EE. UU., 50 símbolos | 60 llamadas/min en REST |
| [Schwab Trader API](https://schwab-py.readthedocs.io/en/latest/streaming.html) | Gratis con cuenta | Streaming en tiempo real (nivel 1 y 2, *time and sales*) | Requiere cuenta en Schwab |
| Interactive Brokers | Suscripciones de datos de pocos dólares | Datos y noticias por API | Requiere cuenta |
| yfinance | Gratis | Datos y noticias de Yahoo | No oficial, con límites de uso agresivos; no apto para tiempo real |
| Massive (plan gratis) | Gratis | Fin de día | Sin intradía |

### 4.4 Redes sociales: estado en 2026

| Plataforma | Estado |
|---|---|
| Reddit | Desde noviembre de 2025 toda nueva app necesita aprobación manual (2-4 semanas), incluso sin fines comerciales; el plan gratuito da 100 consultas/min ([resumen](https://octolens.com/blog/reddit-api-pricing)) |
| StockTwits | [Registro de desarrolladores pausado](https://api.stocktwits.com/developers) y términos que prohíben la extracción automatizada no autorizada |
| X (Twitter) | Pago por uso desde febrero de 2026: US$0,005 por post leído de terceros; ya no hay plan gratuito general ([anuncio](https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476)) |

### 4.5 Datos para backtesting

- **Alpaca:** noticias de Benzinga desde 2015 y barras desde 2016 con la misma cuenta gratuita.
- **[FNSPID](https://github.com/Zdong104/FNSPID_Financial_News_Dataset):** 15,7 millones de noticias
  alineadas con precios de 4.775 empresas del S&P 500 entre 1999 y 2023 (en
  [Hugging Face](https://huggingface.co/datasets/Zihan1004/FNSPID)).
- **EDGAR:** índices completos con fecha y hora de aceptación de cada *filing*.

---

## 5. Repositorios de GitHub

Estrellas aproximadas al 30-sep-2026.

### 5.1 Bots y frameworks que usan noticias

| Repositorio | ★ | Qué es | Para qué sirve aquí |
|---|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | ~109k | Framework multiagente con LLM: analistas de noticias, sentimiento, fundamentales y técnico, investigadores alcista/bajista, *trader* y gestión de riesgo | Ideas de arquitectura; decisiones diarias y uso declarado solo para investigación |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | ~64k | Equipo de agentes LLM que simula un fondo | Educativo; no opera en real |
| [Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | ~2,1k | Framework de trading con backtesting y conexión a 12 brokers (Alpaca, IBKR, Schwab…) | Base para pasar de backtest a *paper* y a real |
| [nicknochnack/MLTradingBot](https://github.com/nicknochnack/MLTradingBot) | ~0,9k | Lumibot + noticias de Alpaca + FinBERT sobre SPY, órdenes *bracket* | Ejemplo mínimo de bot de sentimiento (diario, no intradía) |
| [alpacahq/Momentum-Trading-Example](https://github.com/alpacahq/Momentum-Trading-Example) | ~0,7k | Day trading de momentum: +4 % sobre el cierre previo, ruptura del máximo de los primeros 15 min, MACD positivo, cierre antes del final del día | Esqueleto de momentum intradía (código antiguo, Python 3.6) |
| [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) | ~1k | Servidor MCP oficial de Alpaca: datos, noticias y órdenes desde un LLM; *paper* por defecto | Prototipos con asistentes de IA (revisar cada orden) |

### 5.2 Modelos de lenguaje financiero y sentimiento

| Repositorio | ★ | Nota |
|---|---|---|
| [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) | ~2,2k | El clasificador de sentimiento financiero más usado (modelo `ProsusAI/finbert` en Hugging Face) |
| [yya518/FinBERT](https://github.com/yya518/FinBERT) | ~0,7k | Variante preentrenada en comunicaciones financieras |
| [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | ~21k | LLM financieros abiertos, incluye modelos de sentimiento |
| [AI4Finance-Foundation/FinNLP](https://github.com/AI4Finance-Foundation/FinNLP) | ~1,5k | Recolección de noticias y datos de texto financiero |
| [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | ~8,1k | Plataforma de agentes LLM para finanzas |
| ChronoBERT / ChronoGPT ([Hugging Face](https://huggingface.co/manelalab/chrono-bert-v1-20181231)) | — | Modelos entrenados solo con texto disponible hasta cada fecha: backtests sin sesgo de anticipación |

### 5.3 Acceso a datos y brokers

| Repositorio | ★ | Nota |
|---|---|---|
| [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | ~1,5k | SDK oficial: noticias (REST y WebSocket), datos y órdenes |
| [dgunning/edgartools](https://github.com/dgunning/edgartools) | ~2,8k | Lectura de 8-K, Form 4, 10-K/10-Q y XBRL de EDGAR |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | ~74k | Plataforma abierta de datos para analistas y agentes |
| [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | ~25k | Datos de Yahoo (no oficial) |
| [lit26/finvizfinance](https://github.com/lit26/finvizfinance) | ~1,7k | *Screener*, noticias y datos de *float* de Finviz (scraping) |
| [ib-api-reloaded/ib_async](https://github.com/ib-api-reloaded/ib_async) | ~1,7k | Cliente de Interactive Brokers (sucesor de ib_insync) |
| [massive-com/client-python](https://github.com/massive-com/client-python) | — | Cliente oficial de Massive (ex Polygon) |

### 5.4 Backtesting y motores

| Repositorio | ★ | Nota |
|---|---|---|
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | ~22k | Motor abierto de QuantConnect. Su nube ofrece datasets de noticias de [Benzinga](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/benzinga/benzinga-news-feed) (desde 2016, ~1.250 artículos/día, al segundo) y Tiingo para backtest y en vivo (pueden requerir suscripción); allí está la réplica del ORB |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | ~29,5k | Motor orientado a eventos de nivel producción (Rust + Python) |
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | ~9,2k | Backtesting vectorizado, ideal para barrer parámetros |
| [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | ~9k | Simple y rápido de aprender |

### 5.5 Datasets, aprendizaje y listas

- [stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading) (~21k ★): libro y código con capítulos de NLP sobre noticias.
- [Zdong104/FNSPID_Financial_News_Dataset](https://github.com/Zdong104/FNSPID_Financial_News_Dataset): el dataset de noticias descrito arriba.
- Proyectos históricos cuyo acceso a datos sociales hoy es de pago o requiere aprobación: [shirosaidev/stocksight](https://github.com/shirosaidev/stocksight) (~2,5k ★, Twitter) y [asad70/reddit-sentiment-analysis](https://github.com/asad70/reddit-sentiment-analysis) (Reddit).
- Listas curadas: [wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant) (~30k ★), [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) (~14,5k ★), [georgezouq/awesome-ai-in-finance](https://github.com/georgezouq/awesome-ai-in-finance) (~6,6k ★).

---

## 6. Arquitectura recomendada

```
 Fuentes                     Procesamiento                              Decisión y ejecución
 ────────                    ─────────────                              ────────────────────
 Alpaca News (WebSocket) ─┐
 SEC EDGAR 8-K (Atom)  ───┤   1. Ingesta: guardar hora de la fuente
 Halts Nasdaq (RSS)   ────┼─►    y hora de recepción (mide tu latencia)
 RSS de wires  ───────────┤   2. Deduplicar (misma historia en varias
 Finnhub / TickerTick ────┘      fuentes; actualizaciones)
                              3. Mapear y validar tickers (CIK ↔ ticker)
                              4. Clasificar: reglas → FinBERT → LLM
                                 (el LLM solo para candidatos)
                              5. Filtro de mercado: RVOL, gap, precio, ──► 6. Setup (ORB, VWAP, halt)
                                 float, spread, ATR, halts, SSR               7. Riesgo: % fijo por operación,
                                                                                 pérdida diaria máxima
                                                                              8. Órdenes límite / bracket
                                                                                 (paper → real)
                                                                              9. Registro de todo y métricas
```

Detalles que marcan la diferencia:

1. **Tiempos:** guarda la hora de publicación de la fuente y la hora en que tú la recibiste. La
   diferencia es tu latencia real y es la que debes usar en los backtests.
2. **Deduplicación:** la misma noticia llega por el wire, por Benzinga y por EDGAR; Alpaca además
   envía actualizaciones del mismo artículo (`updated_at`).
3. **Tickers:** valida contra la lista de la SEC o de tu broker; los *cashtags* dan falsos
   positivos (un comunicado puede mencionar un ETF u otra empresa).
4. **Clasificación por capas:** palabras clave primero ("pricing of", "offering", "definitive
   agreement", "FDA approval", "complete response letter", "raises guidance"); FinBERT después; un
   LLM solo para los pocos candidatos que pasan los filtros de mercado, por costo y latencia.
5. **Filtro de mercado:** el RVOL debe compararse con el volumen acumulado a la misma hora en días
   previos, idealmente con datos consolidados (SIP). El *float* se puede obtener de Finviz o
   yfinance, con calidad variable.
6. **Riesgo:** riesgo fijo por operación (0,5-1 % del capital), pérdida diaria máxima (p. ej. 2-3R),
   número máximo de operaciones, nada de promediar a la baja y órdenes límite (nunca a mercado en
   small caps ilíquidas ni fuera de horario).
7. **Registro:** cada noticia, decisión, orden, ejecución y slippage. Sin esto no se puede saber qué
   tipo de catalizador funciona.

---

## 7. Código de ejemplo

### 7.1 Monitor gratuito de catalizadores (probado)

[`ejemplos/monitor_noticias_gratis.py`](ejemplos/monitor_noticias_gratis.py) consulta sin API key
los 8-K de EDGAR, los halts de Nasdaq y los RSS de GlobeNewswire, Business Wire y PR Newswire;
normaliza, deduplica, extrae tickers y descarta los avisos de bufetes.

```bash
cd investigacion/daytrading-noticias/ejemplos
pip install -r requirements.txt
export SEC_USER_AGENT="Tu Nombre tu@email.com"
python monitor_noticias_gratis.py --una-vez   # o sin --una-vez para sondear cada 60 s
```

Salida real del 30-sep-2026 (horas en UTC, recortada):

```
21:30:41Z [SEC 8-K] ONEN: 8-K - ONE Nuclear Energy Inc. (0001846416) (Filer)
           -> 1.01 acuerdo material; 3.02 venta de acciones no registradas; 5.02 cambio de directivos; 8.01 otros eventos
23:50:00Z [HALT] SHFS: SHF Holdings, Inc. Cl A Cmn
           -> T1 noticia pendiente | halt 19:50:00.000 ET
19:50:23Z [HALT] CTNM: Contineum Therapeutics Cl A CS
           -> LUDP pausa por volatilidad (LULD) | halt 15:50:23.030 ET | reanuda 16:00:00 ET
00:30:00Z [GlobeNewswire] APO: Apollo Funds Announce Completion of Acquisition of Nippon Sheet Glass, ...
20:30:00Z [Business Wire] CW: Curtiss-Wright to Announce Third Quarter 2026 Financial Results
```

### 7.2 Noticias en tiempo real de Alpaca + sentimiento con FinBERT

Requiere claves de Alpaca (gratis con cuenta *paper*), `alpaca-py`, `transformers` y `torch`. Las
firmas se verificaron con alpaca-py 0.44; no se ejecutó contra el servicio real.

```python
import os

from alpaca.data.live.news import NewsDataStream
from transformers import pipeline

finbert = pipeline("text-classification", model="ProsusAI/finbert")  # ~440 MB la primera vez
stream = NewsDataStream(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"])


async def al_recibir(noticia):
    s = finbert(noticia.headline)[0]  # {'label': 'positive'|'negative'|'neutral', 'score': ...}
    print(noticia.created_at, noticia.symbols, s["label"], round(s["score"], 2), noticia.headline)


stream.subscribe_news(al_recibir, "*")  # "*" = todas las noticias; o tickers concretos
stream.run()
```

Para históricos (backtesting): `NewsClient(...).get_news(NewsRequest(symbols="AAPL", start=..., end=...))`
de `alpaca.data.historical.news`, paginando con `page_token`.

### 7.3 Filtro de mercado con un *snapshot*

```python
import os

from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest

datos = StockHistoricalDataClient(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"])


def candidatos(simbolos, precio_min=2, precio_max=20, gap_min=0.10):
    snaps = datos.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=simbolos, feed=DataFeed.IEX))
    salida = []
    for sym, s in snaps.items():
        if not (s.latest_trade and s.daily_bar and s.previous_daily_bar):
            continue
        precio = s.latest_trade.price
        gap = precio / s.previous_daily_bar.close - 1
        # RVOL aproximado: volumen de hoy frente al día completo de ayer (ambos solo de IEX).
        rvol = s.daily_bar.volume / max(s.previous_daily_bar.volume, 1)
        if precio_min <= precio <= precio_max and gap >= gap_min:
            salida.append((sym, round(gap * 100, 1), round(rvol, 1)))
    return sorted(salida, key=lambda x: -x[2])
```

Con el plan gratuito el volumen es solo el de IEX; para un RVOL fiable hay que comparar el volumen
acumulado a la misma hora con el de días anteriores usando datos SIP.

### 7.4 Orden *bracket* en *paper trading*

```python
import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest

broker = TradingClient(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"], paper=True)
broker.submit_order(LimitOrderRequest(
    symbol="XYZ", qty=100, side=OrderSide.BUY, limit_price=5.10, time_in_force=TimeInForce.DAY,
    order_class=OrderClass.BRACKET,
    take_profit=TakeProfitRequest(limit_price=5.60),  # +2R
    stop_loss=StopLossRequest(stop_price=4.85),       # 1R = 0,25
))
```

### 7.5 Clasificación de titulares con un LLM (opcional, de pago)

Útil para separar "oferta de acciones" de "contrato" o "FDA", o para marcar repeticiones. Usa la
API de Claude con salida JSON validada por esquema. Se verificó que la petición se construye
correctamente con `anthropic` 1.9 (sin llamar al servicio). `fallbacks="default"` hace que, si el
modelo declina la petición, la API la reintente con el modelo recomendado en la misma llamada.

```python
import json

import anthropic

client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno

ESQUEMA = {
    "type": "object",
    "properties": {
        "evento": {"type": "string", "enum": [
            "resultados", "guidance", "fda_ensayo", "fusion_adquisicion", "oferta_dilucion",
            "contrato_alianza", "analistas", "legal_regulatorio", "insiders", "macro", "otro"]},
        "direccion": {"type": "string", "enum": ["alcista", "bajista", "neutral"]},
        "impacto": {"type": "string", "enum": ["bajo", "medio", "alto"]},
        "es_nueva": {"type": "boolean"},
        "motivo": {"type": "string"},
    },
    "required": ["evento", "direccion", "impacto", "es_nueva", "motivo"],
    "additionalProperties": False,
}
SISTEMA = ("Clasificas titulares bursátiles de EE. UU. para trading intradía. "
           "Impacto 'alto' solo si la noticia puede mover la acción más de 5% hoy. "
           "es_nueva=false si es un recordatorio, una repetición o publicidad de bufetes.")


def clasificar(ticker: str, titular: str) -> dict | None:
    resp = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=1024,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        system=SISTEMA,
        messages=[{"role": "user", "content": f"Ticker: {ticker}\nTitular: {titular}"}],
    )
    if resp.stop_reason in ("refusal", "max_tokens"):
        return None
    texto = next(b.text for b in resp.content if b.type == "text")
    return json.loads(texto)
```

Costo orientativo: Claude Opus 5.5 cuesta US$4 por millón de tokens de entrada y US$20 por millón
de salida; con unos 400 tokens de entrada y ~150 de salida, un titular ronda **US$0,005**, o sea
unos US$5 por cada 1.000 titulares (mídelo con `resp.usage`). Por eso conviene clasificar solo lo
que ya pasó los filtros de mercado. Si priorizas costo, la tabla de precios incluye modelos más
baratos (p. ej. Claude Haiku 4.5, US$1/US$5 por millón). Para reclasificar históricos sin prisa,
la Batch API cuesta la mitad (no admite `fallbacks`).

### 7.6 Pseudocódigo del ORB en Stocks in Play

```
cada día hábil:
  universo = acciones con apertura > 5, volumen medio 14d >= 1M y ATR14 > 0,50
  a las 9:35 ET:
    rvol[s] = volumen(9:30-9:35) / promedio de volumen(9:30-9:35) de los 14 días previos
    elegidas = top 20 por rvol con rvol >= 1
    para s en elegidas:
      si vela 5m alcista: stop de compra en máximo 5m
      si vela 5m bajista: stop de venta en corto en mínimo 5m
      stop de protección = entrada ∓ 0,10 * ATR14
      tamaño = (1% del capital) / (0,10 * ATR14), con apalancamiento total <= 4x
  a las 16:00 ET: cerrar todo
```

---

## 8. Backtesting sin engañarse

- **Tiempos *point-in-time*:** usa la hora en que la noticia estuvo disponible (`created_at` en
  Alpaca, hora de aceptación en EDGAR) más tu latencia, nunca la fecha del artículo. Cuidado con
  las revisiones (`updated_at`).
- **Sesgo de anticipación de los LLM:** un modelo entrenado con datos posteriores "sabe" qué pasó.
  Usa modelos con fecha de corte anterior al período de prueba (ChronoBERT/ChronoGPT) o anonimiza
  la empresa en el titular ([Glasserman y Lin](https://arxiv.org/abs/2309.17322)).
- **Supervivencia:** incluye las small caps que luego quebraron o dejaron de cotizar.
- **Costos reales:** spread, slippage (enorme en aperturas y reanudaciones de halts), comisiones y
  tasas regulatorias, costo de préstamo y *locates* para cortos, halts que impiden salir.
- **Sobreajuste:** barre parámetros y mira la estabilidad, no el mejor resultado; valida fuera de
  muestra (*walk-forward*).
- **Paper trading** de 1 a 3 meses con las mismas reglas antes de arriesgar dinero; mide
  expectativa por operación (en R), acierto, *drawdown* y resultados por tipo de catalizador.

---

## 9. Regulación y aspectos prácticos en 2026

- **Fin de la regla PDT (EE. UU.):** la SEC aprobó el 14 de abril de 2026 los cambios de FINRA a la
  Regla 4210 que eliminan el mínimo de US$25.000 y la figura de *pattern day trader*; entró en vigor
  el 4 de junio de 2026 y los brokers tienen hasta el 20 de octubre de 2027 para implementarla. Se
  reemplaza por requisitos de margen intradía según la exposición de cada momento; cada broker fija
  el poder de compra intradía ([FINRA](https://www.finra.org/compliance-tools/weekly-archive/04152026),
  [Schwab](https://www.schwab.com/learn/story/sec-approves-scrapping-25000-day-trader-minimum)).
  Pregunta a tu broker cuándo lo aplica.
- **Negociación casi 24 horas:** la SEC aprobó en abril de 2026 que Nasdaq pase a 23 horas diarias,
  5 días a la semana; Nasdaq y NYSE planean empezar el 6 de diciembre de 2026, con una sesión
  nocturna de 21:00 a 4:00 ET, bandas de precio de 20 % al inicio y acceso a través de brokers
  miembros ([Jones Day](https://www.jonesday.com/en/insights/2026/09/nyse-and-nasdaq-move-to-23hour-trading-day-overnight-session-is-an-evolution-but-not-yet-a-revolution)).
  Más noticias se podrán operar fuera del horario clásico, pero con poca liquidez.
- **Restricción de ventas en corto (SSR, Regla 201):** si una acción cae 10 % o más frente al cierre
  previo, el resto del día y el siguiente solo se puede vender en corto por encima del mejor bid
  ([SEC](https://www.sec.gov/newsroom/press-releases/2010-26-sec-approves-short-selling-restrictions)).
- **Pausas LULD y halts T1:** pueden dejarte atrapado; dimensiona pensando en ello.
- **Fuera de EE. UU.:** la disponibilidad de Alpaca, IBKR o Schwab varía por país, al igual que la
  fiscalidad de las ganancias de corto plazo. Verifícalo antes de abrir cuenta.

---

## 10. Plan de acción sugerido

1. **Semanas 1-2, observar:** abrir cuenta *paper* en Alpaca, correr el monitor gratuito y el
   WebSocket de noticias, y guardar todo en una base de datos (SQLite basta).
2. **Semanas 3-4, escanear:** construir el filtro de mercado (RVOL, gap, precio, *float*) y elegir
   1-2 *setups*: ORB en Stocks in Play y reanudación de halts con confirmación.
3. **Mes 2, backtest:** noticias históricas de Alpaca (desde 2015) y barras de minuto (desde 2016); medir la
   expectativa por tipo de catalizador; decidir si FinBERT o un LLM mejoran el filtro.
4. **Mes 3, paper trading en vivo** con reglas fijas y revisión semanal. Considerar datos SIP
   (US$99/mes en Alpaca) si la estrategia depende del volumen.
5. **Solo si los números aguantan:** capital real pequeño, con pérdida diaria máxima automática.

---

## 11. Fuentes

**Académicas**

- [Busse y Green (2002), *Market efficiency in real time*](https://www.sciencedirect.com/science/article/abs/pii/S0304405X02001484)
- [Chan (2003), *Stock price reaction to news and no-news: drift and reversal after headlines*](https://ideas.repec.org/a/eee/jfinec/v70y2003i2p223-260.html)
- [Gervais, Kaniel y Mingelgrin (2001), *The High-Volume Return Premium*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=146468)
- [Barber y Odean (2008), *All That Glitters*](https://academic.oup.com/rfs/article-abstract/21/2/785/1607197)
- [Rogers, Skinner y Zechman (2016), *The role of the media in disseminating insider-trading news*](https://link.springer.com/article/10.1007/s11142-016-9354-2)
- [Zarattini, Barbon y Aziz (2024), *A Profitable Day Trading Strategy For The U.S. Equity Market*](https://ideas.repec.org/p/chf/rpseri/rp2498.html) y [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284)
- [Lopez-Lira y Tang, *Can ChatGPT Forecast Stock Price Movements?*](https://arxiv.org/abs/2304.07619)
- [Chen, Kelly y Xiu, *Expected Returns and Large Language Models*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687)
- [Glasserman y Lin, *Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis*](https://arxiv.org/abs/2309.17322)
- [He, Lv, Manela y Wu, *Chronologically Consistent Large Language Models*](https://arxiv.org/abs/2502.21206)
- [Chague, De-Losso y Giovannetti, *Day Trading for a Living?*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- [FNSPID: A Comprehensive Financial News Dataset in Time Series](https://arxiv.org/abs/2402.06698)
- [Revisión de la literatura sobre PEAD](https://www.sciencedirect.com/science/article/pii/S2214635020303750)

**Páginas especializadas**

- [QuantConnect: ORB for Stocks in Play](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/)
- [Quantpedia: Post-Earnings Announcement Effect](https://quantpedia.com/strategies/post-earnings-announcement-effect)
- [Alpaca Learn: sentimiento con News API y transformers](https://alpaca.markets/learn/sentiment-analysis-with-news-api-and-transformers)
- [Warrior Trading: Finding Stocks to Day Trade](https://www.warriortrading.com/finding-stocks-to-day-trade/)
- [CapTrader: Newstrading as a day trading strategy](https://www.captrader.com/en/blog/newstrading/)
- [Quantra: News Based Trading](https://quantra.quantinsti.com/glossary/News-Based-Trading)
- [TradingSim: dilución y ofertas](https://www.tradingsim.com/blog/stock-dilution-and-offerings-explained-for-beginners-tradingsim)
- [DilutionTracker: ofertas y small caps](https://knowledge.dilutiontracker.com/en/articles/5722415-offerings-investment-bank-tiers-and-why-it-matters-for-small-cap-stocks)
- [Benzinga: sistemas de trading ante IPC, FOMC e imprevistos](https://www.benzinga.com/Opinion/26/06/53097073/trading-systems-and-market-news-how-to-handle-cpi-fomc-and-unexpected-events)
- [Nasdaq Trader: códigos de halts](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes)

**APIs y documentación**

- [Alpaca: noticias en tiempo real](https://docs.alpaca.markets/us/docs/streaming-real-time-news), [noticias históricas](https://docs.alpaca.markets/docs/historical-news-data), [planes de datos](https://docs.alpaca.markets/docs/about-market-data-api)
- [Finnhub](https://finnhub.io/docs/api/market-news) · [Massive](https://massive.com/pricing) · [Alpha Vantage](https://www.alphavantage.co/premium/) · [Marketaux](https://www.marketaux.com/pricing) · [EODHD](https://eodhd.com/financial-apis/stock-market-financial-news-api) · [TickerTick](https://github.com/hczhu/TickerTick-API) · [GDELT](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) · [NewsAPI](https://newsapi.org/pricing) · [Tiingo](https://www.tiingo.com/about/pricing)
- [SEC: recursos para desarrolladores](https://www.sec.gov/about/developer-resources) · [APIs de EDGAR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Nasdaq: RSS de halts](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltRSS) · [GlobeNewswire RSS](https://www.globenewswire.com/rss/list) · [PR Newswire RSS](https://www.prnewswire.com/rss/) · [Business Wire feeds](https://www.businesswire.com/help/feed-options)
- [IBKR: noticias por API](https://interactivebrokers.github.io/tws-api/news.html) · [sec-api.io](https://sec-api.io/) · [Stock Titan](https://www.stocktitan.net/pricing) · [rtpr.io](https://rtpr.io/)
- [Reddit API 2026](https://octolens.com/blog/reddit-api-pricing) · [StockTwits Developers](https://api.stocktwits.com/developers) · [X API pago por uso](https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476)

**Regulación**

- [FINRA: nuevas normas de margen intradía](https://www.finra.org/compliance-tools/weekly-archive/04152026) · [Schwab: fin del mínimo de US$25.000](https://www.schwab.com/learn/story/sec-approves-scrapping-25000-day-trader-minimum)
- [Jones Day: NYSE y Nasdaq a 23 horas](https://www.jonesday.com/en/insights/2026/09/nyse-and-nasdaq-move-to-23hour-trading-day-overnight-session-is-an-evolution-but-not-yet-a-revolution)
- [SEC: regla alternativa de *uptick* (Regla 201)](https://www.sec.gov/newsroom/press-releases/2010-26-sec-approves-short-selling-restrictions)
