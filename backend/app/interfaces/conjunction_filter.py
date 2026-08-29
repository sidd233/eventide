"""Strategy interface for cheap geometric prefilters.

New filters (PATH filter, an ML prefilter, ...) are added by subclassing this and
registering them in the detector's filter chain — no existing code changes
(Open/Closed). Every implementation must be a drop-in substitute for any other
(Liskov): given the same pair it must return a bool and never mutate the inputs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain import ScreeningObject


class ConjunctionFilter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def keep_pair(self, a: ScreeningObject, b: ScreeningObject) -> bool:
        """Return True if the pair *might* conjunct and should survive to the
        next, more expensive stage. Must be conservative: a filter may only drop
        a pair when it is geometrically impossible for them to come close."""
        raise NotImplementedError
