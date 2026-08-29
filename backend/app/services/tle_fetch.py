"""TLE sources. Single responsibility: obtain TLE text and parse it into
:class:`TLE` objects. Caching is an internal concern of each source, exposed only
through the :class:`TLESource` interface.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.domain import TLE
from app.interfaces.tle_source import TLESource

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"


def parse_tle_text(text: str) -> list[TLE]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    out: list[TLE] = []
    i = 0
    n = len(lines)
    while i + 1 < n:
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            name, l1, l2 = f"UNNAMED-{lines[i][2:7]}", lines[i], lines[i + 1]
            i += 2
        elif i + 2 < n and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
            i += 3
        else:
            i += 1
            continue
        try:
            tle = TLE(name=name, line1=l1, line2=l2)
            _ = tle.norad_id
            out.append(tle)
        except ValueError:
            continue
    return out


class StaticTLESource(TLESource):
    """In-memory source for tests and fixtures."""

    def __init__(self, tles: list[TLE]):
        self._tles = list(tles)

    def fetch(self) -> list[TLE]:
        return list(self._tles)


class FileTLESource(TLESource):
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def fetch(self) -> list[TLE]:
        return parse_tle_text(self._path.read_text())


_USER_AGENT = "Eventide/0.1 (space-debris conjunction screening)"


class CelesTrakTLESource(TLESource):
    """Fetches one or more CelesTrak GP groups with a TTL cache.

    Falls back, in order, to the last good cache and then to a bundled snapshot
    (``bootstrap_path``) when the live fetch fails -- CelesTrak blocks many
    datacenter IP ranges, so a deployed instance often cannot reach it and must
    still serve real (if stale) data rather than 500.
    """

    def __init__(
        self,
        groups: list[str],
        ttl_s: int = 3600,
        timeout_s: float = 20.0,
        client: httpx.Client | None = None,
        bootstrap_path: str | Path | None = None,
    ):
        self._groups = list(groups)
        self._ttl_s = ttl_s
        self._timeout_s = timeout_s
        self._client = client
        self._bootstrap_path = Path(bootstrap_path) if bootstrap_path else None
        self._cache: list[TLE] | None = None
        self._cache_time: float = 0.0
        self._cache_is_bootstrap: bool = False
        self.last_error: str | None = None
        self.served_stale: bool = False

    def _age(self) -> float:
        return time.monotonic() - self._cache_time

    def invalidate(self) -> None:
        """Drop the cached TLE set so the next ``fetch()`` re-hits CelesTrak.

        Used by the "recompute everything" action so a manual refresh really
        pulls fresh element sets instead of reusing the TTL cache.
        """
        self._cache = None
        self._cache_time = 0.0
        self._cache_is_bootstrap = False

    def _bootstrap(self) -> list[TLE] | None:
        if self._bootstrap_path is None:
            return None
        try:
            tles = parse_tle_text(self._bootstrap_path.read_text())
        except OSError:
            return None
        return tles or None

    def fetch(self) -> list[TLE]:
        if self._cache is not None and self._age() < self._ttl_s:
            self.served_stale = self._cache_is_bootstrap
            return list(self._cache)

        client = self._client or httpx.Client(
            timeout=httpx.Timeout(self._timeout_s, connect=6.0),
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),  # force IPv4
        )
        owns_client = self._client is None
        try:
            merged: dict[int, TLE] = {}
            for group in self._groups:
                resp = client.get(
                    CELESTRAK_GP_URL, params={"GROUP": group, "FORMAT": "tle"}
                )
                resp.raise_for_status()
                for tle in parse_tle_text(resp.text):
                    merged.setdefault(tle.norad_id, tle)
            if not merged:
                raise RuntimeError("CelesTrak returned no usable TLEs")
            self._cache = list(merged.values())
            self._cache_time = time.monotonic()
            self._cache_is_bootstrap = False
            self.last_error = None
            self.served_stale = False
            return list(self._cache)
        except Exception as exc:  # noqa: BLE001 - fall back to cache, then bundle
            self.last_error = f"{type(exc).__name__}: {exc}"
            if self._cache is not None:
                self.served_stale = self._cache_is_bootstrap
                return list(self._cache)
            bootstrap = self._bootstrap()
            if bootstrap is not None:
                self._cache = bootstrap
                self._cache_time = time.monotonic()
                self._cache_is_bootstrap = True
                self.served_stale = True
                return list(bootstrap)
            raise
        finally:
            if owns_client:
                client.close()
