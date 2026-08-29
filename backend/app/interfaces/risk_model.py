"""Strategy interface for collision-probability models.

``FosterEstesModel`` is the first implementation; Chan, Alfano, or a Monte-Carlo
model can be substituted without touching ``assess.py`` (Dependency Inversion).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain import ConjunctionEvent


class RiskModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def collision_probability(self, event: ConjunctionEvent) -> float:
        """Return the probability of collision for a single conjunction event.

        Must be monotonic: holding relative geometry and covariance fixed, a
        smaller miss distance must not yield a smaller probability.
        """
        raise NotImplementedError
