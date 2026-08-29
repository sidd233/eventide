"""Abstraction for anything that yields a set of TLEs.

Kept intentionally narrow (Interface Segregation): a consumer that only needs
TLEs must not be forced to depend on caching or ephemeris-storage methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain import TLE


class TLESource(ABC):
    @abstractmethod
    def fetch(self) -> list[TLE]:
        """Return the current set of TLEs. Implementations may cache internally."""
        raise NotImplementedError
