"""Risk assessment: turn detected conjunctions into ranked, tiered alerts.

Depends on the :class:`RiskModel` abstraction, injected at construction, so the
Pc method can be swapped without changing this module.
"""
from __future__ import annotations

import math

from app.domain import ConjunctionEvent
from app.interfaces.risk_model import RiskModel

TIERS = ("Low", "Medium", "High")


class RiskAssessor:
    def __init__(
        self,
        risk_model: RiskModel,
        *,
        pc_high: float = 1e-4,
        pc_medium: float = 1e-6,
        window_hours: float = 48.0,
    ):
        self._model = risk_model
        self._pc_high = pc_high
        self._pc_medium = pc_medium
        self._window_hours = window_hours

    def assess(self, events: list[ConjunctionEvent]) -> list[ConjunctionEvent]:
        for ev in events:
            pc = self._model.collision_probability(ev)
            ev.pc = pc
            ev.risk_score = self._score(ev, pc)
            ev.risk_tier = self._tier(pc, ev.risk_score)
        events.sort(key=lambda e: (e.risk_score or 0.0), reverse=True)
        return events

    # -- internals -------------------------------------------------------
    def _score(self, ev: ConjunctionEvent, pc: float) -> float:
        # Pc mapped log-linearly: 1e-9 -> 0, 1e0 -> 1.
        pc_c = min(1.0, max(0.0, (math.log10(pc) + 9.0) / 9.0)) if pc > 0 else 0.0
        tca_h = ev.tca_s / 3600.0
        urgency = min(1.0, max(0.0, 1.0 - tca_h / max(self._window_hours, 1e-6)))
        closeness = min(1.0, max(0.0, 1.0 - ev.miss_distance_km / 10.0))
        return round(0.7 * pc_c + 0.2 * urgency + 0.1 * closeness, 4)

    def _tier(self, pc: float, score: float) -> str:
        if pc >= self._pc_high:
            return "High"
        if pc >= self._pc_medium:
            return "Medium"
        # Very close geometry still warrants attention even at low modelled Pc.
        if score >= 0.5:
            return "Medium"
        return "Low"
