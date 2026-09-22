"""Cliente HTTP con reintentos y caché en memoria."""
from __future__ import annotations

import time
from typing import Any

import requests

_session = requests.Session()
_cache: dict[tuple, tuple[float, Any]] = {}


class SourceError(RuntimeError):
    pass


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: float = 20.0, retries: int = 3, ttl: float = 60.0, as_text: bool = False) -> Any:
    key = (url, tuple(sorted((params or {}).items())), as_text)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.text if as_text else r.json()
            _cache[key] = (time.time(), data)
            return data
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            time.sleep(0.5 * 2 ** attempt)
    raise SourceError(f"GET {url} falló: {last_exc}")
