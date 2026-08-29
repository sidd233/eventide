"""Geometric conjunction prefilters (strategy implementations).

Add a new prefilter by subclassing :class:`ConjunctionFilter` and inserting it
into the detector's chain; nothing here or in ``detect.py`` needs to change.
"""
from __future__ import annotations

from app.domain import ScreeningObject
from app.interfaces.conjunction_filter import ConjunctionFilter


class ApsisFilter(ConjunctionFilter):
    """Perigee/apogee altitude-band filter (a.k.a. the "smart sieve" first
    stage). Two objects can only conjunct if their radial altitude ranges
    overlap. Cheap, and conservative: it never drops a pair that could actually
    come close, because it ignores phasing entirely.
    """

    def __init__(self, pad_km: float = 15.0):
        self._pad_km = pad_km

    @property
    def name(self) -> str:
        return "apsis"

    def keep_pair(self, a: ScreeningObject, b: ScreeningObject) -> bool:
        lo_a, hi_a = a.perigee_alt_km - self._pad_km, a.apogee_alt_km + self._pad_km
        lo_b, hi_b = b.perigee_alt_km - self._pad_km, b.apogee_alt_km + self._pad_km
        return lo_a <= hi_b and lo_b <= hi_a


class AcceptAllFilter(ConjunctionFilter):
    """No-op baseline, useful for measuring another filter's reduction rate."""

    @property
    def name(self) -> str:
        return "accept-all"

    def keep_pair(self, a: ScreeningObject, b: ScreeningObject) -> bool:
        return True
