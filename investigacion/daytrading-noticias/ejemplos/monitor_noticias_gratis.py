#!/usr/bin/env python3
"""Monitor de noticias bursátiles con fuentes gratuitas y sin API key.

Fuentes:
  - SEC EDGAR: feed Atom de los últimos 8-K (eventos materiales).
  - Nasdaq Trader: feed RSS de halts (T1 = noticia pendiente, LUDP = pausa LULD...).
  - GlobeNewswire, Business Wire y PR Newswire: RSS de comunicados de prensa.

Solo LEE datos públicos y los imprime como eventos normalizados; no opera.
Los feeds gratuitos llegan con minutos de retraso frente a feeds de pago:
sirve para aprender, hacer paper trading y construir la capa de ingesta.

Uso:
    pip install -r requirements.txt
    export SEC_USER_AGENT="Tu Nombre tu@email.com"   # la SEC exige identificarse
    python monitor_noticias_gratis.py --una-vez      # una pasada y termina
    python monitor_noticias_gratis.py                # sondeo continuo
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests

SEC_8K_ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K"
               "&company=&dateb=&owner=include&start=0&count=40&output=atom")
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
NASDAQ_HALTS = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
GLOBENEWSWIRE = ("https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/"
                 "GlobeNewswire%20-%20News%20about%20Public%20Companies")
BUSINESSWIRE = "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJcFVJYWQ=="
PRNEWSWIRE = "https://www.prnewswire.com/rss/all-news-releases-list.rss"
ET = ZoneInfo("America/New_York")  # los halts de Nasdaq vienen en hora de Nueva York

# Ítems de 8-K con más relevancia para trading intradía.
ITEMS_8K = {
    "1.01": "acuerdo material", "1.03": "quiebra", "1.05": "incidente ciber",
    "2.02": "resultados", "2.05": "reestructuración", "3.01": "aviso de exclusión",
    "3.02": "venta de acciones no registradas", "4.02": "no confiabilidad de estados",
    "5.02": "cambio de directivos", "7.01": "Reg FD", "8.01": "otros eventos",
}
# Motivos de halt de Nasdaq (https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes).
HALTS = {
    "T1": "noticia pendiente", "T2": "noticia publicada", "T12": "Nasdaq pide información",
    "LUDP": "pausa por volatilidad (LULD)", "LUDS": "pausa LULD (straddle)",
    "M": "pausa por volatilidad (otra bolsa)", "H10": "suspensión de la SEC",
    "H4": "incumplimiento", "M1": "acción corporativa",
}
# Titulares de bufetes buscando demandantes: ruido sin información nueva.
SPAM = re.compile(r"(investors? (have|who)|urges .* (stock|share)holders|class action|"
                  r"securities fraud|investor alert|shareholder alert|deadline alert|"
                  r"investigation (notice|alert)|notifies investors|law firm|lawsuit filed)", re.I)
BOLSAS_US = ("NASDAQ", "NYSE", "AMEX", "CBOE")
TICKER_PRN = re.compile(r"\((?:NYSE|NASDAQ|Nasdaq|AMEX|Cboe)[^:)]*:\s*([A-Z][A-Z.\-]{0,6})\)")


@dataclass
class Evento:
    fuente: str
    uid: str
    hora_utc: datetime | None
    tickers: list[str]
    titulo: str
    url: str
    detalle: str = ""


@dataclass
class Monitor:
    user_agent: str
    todos: bool = False
    vistos: set[str] = field(default_factory=set)
    cik_a_ticker: dict[int, str] = field(default_factory=dict)

    def get(self, url: str) -> bytes:
        resp = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=20)
        resp.raise_for_status()
        return resp.content

    def feed(self, url: str) -> list:
        parsed = feedparser.parse(self.get(url))
        if parsed.bozo and not parsed.entries:  # p. ej. una página HTML en lugar del RSS
            raise ValueError(f"respuesta no es un feed válido: {url}")
        return parsed.entries

    def cargar_tickers(self) -> None:
        data = json.loads(self.get(SEC_TICKERS))
        # Un CIK puede tener varios tickers (clases, warrants, units); el primero es el principal.
        for fila in data.values():
            self.cik_a_ticker.setdefault(fila["cik_str"], fila["ticker"])

    # --- Parsers: cada uno devuelve eventos normalizados -------------------
    def sec_8k(self) -> list[Evento]:
        eventos = []
        for e in self.feed(SEC_8K_ATOM):
            cik = re.search(r"\((\d{10})\)", e.title)
            ticker = self.cik_a_ticker.get(int(cik.group(1))) if cik else None
            items = re.findall(r"Item (\d\.\d\d)", e.get("summary", ""))
            relevantes = [f"{i} {ITEMS_8K[i]}" for i in items if i in ITEMS_8K]
            eventos.append(Evento("SEC 8-K", e.id, _hora(e, "updated_parsed"),
                                  [ticker] if ticker else [], e.title, e.link,
                                  "; ".join(relevantes) or "; ".join(items)))
        return eventos

    def halts(self) -> list[Evento]:
        eventos = []
        for e in self.feed(NASDAQ_HALTS):
            codigo = e.get("ndaq_reasoncode", "")
            simbolo = e.get("ndaq_issuesymbol", "")
            reanuda = e.get("ndaq_resumptiontradetime", "")
            uid = f"{simbolo}|{e.get('ndaq_haltdate')}|{e.get('ndaq_halttime')}|{reanuda}"
            detalle = f"{codigo} {HALTS.get(codigo, '')} | halt {e.get('ndaq_halttime', '')} ET"
            if reanuda:
                detalle += f" | reanuda {reanuda} ET"
            eventos.append(Evento("HALT", uid, _hora_halt(e), [simbolo],
                                  e.get("ndaq_issuename", ""), NASDAQ_HALTS, detalle))
        return eventos

    def globenewswire(self) -> list[Evento]:
        eventos = []
        for e in self.feed(GLOBENEWSWIRE):
            tickers = [t["term"].split(":", 1)[1] for t in e.get("tags", [])
                       if (t.get("scheme") or "").endswith("/rss/stock")
                       and t["term"].upper().startswith(BOLSAS_US)]
            eventos.append(Evento("GlobeNewswire", e.id, _hora(e, "published_parsed"),
                                  tickers, e.title, e.link))
        return eventos

    def businesswire(self) -> list[Evento]:
        eventos = []
        for e in self.feed(BUSINESSWIRE)[:100]:
            texto = f"{e.title} {e.get('summary', '')}"
            tickers = sorted(set(re.findall(r"\$([A-Z]{1,5})\b", texto)))
            eventos.append(Evento("Business Wire", e.id, _hora(e, "published_parsed"),
                                  tickers, e.title, e.link))
        return eventos

    def prnewswire(self) -> list[Evento]:
        eventos = []
        for e in self.feed(PRNEWSWIRE):
            tickers = sorted(set(TICKER_PRN.findall(f"{e.title} {e.get('summary', '')}")))
            eventos.append(Evento("PR Newswire", e.id, _hora(e, "published_parsed"),
                                  tickers, e.title, e.link))
        return eventos

    # --- Bucle -------------------------------------------------------------
    def nuevos(self, eventos: list[Evento]) -> list[Evento]:
        salida = []
        for ev in eventos:
            if ev.uid in self.vistos:
                continue
            self.vistos.add(ev.uid)
            if not self.todos and (not ev.tickers or SPAM.search(ev.titulo)):
                continue
            salida.append(ev)
        return salida


def _hora(entry, campo: str) -> datetime | None:
    t = entry.get(campo)
    return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc) if t else None


def _hora_halt(entry) -> datetime | None:
    try:
        local = datetime.strptime(f"{entry.get('ndaq_haltdate')} {entry.get('ndaq_halttime', '')[:8]}",
                                  "%m/%d/%Y %H:%M:%S")
    except ValueError:
        return None
    return local.replace(tzinfo=ET).astimezone(timezone.utc)


def imprimir(ev: Evento) -> None:
    hora = ev.hora_utc.strftime("%H:%M:%SZ") if ev.hora_utc else "--:--:--"
    tickers = ",".join(ev.tickers) or "?"
    linea = f"{hora} [{ev.fuente}] {tickers}: {ev.titulo[:110]}"
    print(linea + (f"\n           -> {ev.detalle}" if ev.detalle else ""), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--una-vez", action="store_true", help="una sola pasada y salir")
    ap.add_argument("--intervalo", type=int, default=60,
                    help="segundos entre sondeos (mínimo 60 por las reglas de Nasdaq)")
    ap.add_argument("--primeros", type=int, default=5,
                    help="eventos a mostrar por fuente en la primera pasada")
    ap.add_argument("--todos", action="store_true",
                    help="incluir eventos sin ticker de EE. UU. y avisos de bufetes")
    args = ap.parse_args()

    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        print("Define SEC_USER_AGENT='Tu Nombre tu@email.com' (lo exige la SEC).", file=sys.stderr)
        return 2
    mon = Monitor(user_agent=user_agent, todos=args.todos)
    mon.cargar_tickers()
    fuentes = [mon.sec_8k, mon.halts, mon.globenewswire, mon.businesswire, mon.prnewswire]
    intervalo = max(args.intervalo, 60)

    primera = True
    while True:
        for fuente in fuentes:
            try:
                eventos = mon.nuevos(fuente())
            except (requests.RequestException, ValueError, AttributeError, KeyError) as exc:
                print(f"[aviso] {fuente.__name__}: {exc}", file=sys.stderr)
                continue
            for ev in (eventos[:args.primeros] if primera else eventos):
                imprimir(ev)
        if args.una_vez:
            return 0
        primera = False
        time.sleep(intervalo)


if __name__ == "__main__":
    sys.exit(main())
