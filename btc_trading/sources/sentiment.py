"""Psicología: Fear & Greed (alternative.me), titulares (RSS), tendencias (CoinGecko)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import pandas as pd

from .http import get

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/",
]

POSITIVE = {"surge", "rally", "soar", "jump", "gain", "bull", "bullish", "record", "high", "approve",
            "approval", "inflow", "inflows", "adopt", "adoption", "buy", "buying", "accumulate", "breakout",
            "rebound", "recover", "recovery", "upgrade", "etf", "reserve", "institutional", "optimism"}
NEGATIVE = {"crash", "plunge", "drop", "fall", "slump", "bear", "bearish", "sell", "selloff", "sell-off",
            "outflow", "outflows", "hack", "hacked", "exploit", "ban", "lawsuit", "sec", "fraud", "liquidation",
            "liquidations", "fear", "dump", "decline", "low", "warning", "risk", "collapse", "bankrupt", "tariff"}
BTC_RE = re.compile(r"\b(bitcoin|btc)\b", re.I)


def fear_greed(limit: int = 0) -> pd.Series:
    js = get("https://api.alternative.me/fng/", {"limit": limit, "format": "json"}, ttl=3600)
    s = pd.Series({pd.Timestamp(int(d["timestamp"]), unit="s", tz="UTC"): float(d["value"]) for d in js["data"]})
    return s.sort_index().rename("fear_greed")


def headline_score(text: str) -> float:
    words = re.findall(r"[a-z\-]+", text.lower())
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


def news(hours: int = 24) -> pd.DataFrame:
    """Titulares recientes que mencionan Bitcoin, con puntuación léxica [-1, 1]."""
    rows = []
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=hours)
    for url in RSS_FEEDS:
        try:
            root = ET.fromstring(get(url, as_text=True, ttl=600))
        except Exception:  # noqa: BLE001
            continue
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
            try:
                ts = pd.Timestamp(parsedate_to_datetime(item.findtext("pubDate"))).tz_convert("UTC")
            except Exception:  # noqa: BLE001
                continue
            if ts < cutoff or not BTC_RE.search(title + " " + desc):
                continue
            rows.append({"ts": ts, "source": url.split("/")[2], "title": title,
                         "score": headline_score(title + " " + desc[:300])})
    return pd.DataFrame(rows, columns=["ts", "source", "title", "score"]).sort_values("ts")


def coingecko_trending_rank(coin_id: str = "bitcoin") -> int | None:
    """Posición de BTC en trending de CoinGecko (proxy de atención/social volume)."""
    js = get("https://api.coingecko.com/api/v3/search/trending", ttl=600)
    for i, c in enumerate(js.get("coins", []), 1):
        if c.get("item", {}).get("id") == coin_id:
            return i
    return None
