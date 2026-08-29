"""Labelled synthetic conjunction set used to measure the risk model's
false-negative rate. Run once at startup so ``/metrics`` always reports a real
recall number, not a placeholder.
"""
from __future__ import annotations

import numpy as np

from app.domain import ConjunctionEvent
from app.interfaces.risk_model import RiskModel
from app.services.assess import RiskAssessor

# "Dangerous" == the two objects pass within this distance. Every such case must
# score at or above the medium-risk Pc threshold.
DANGEROUS_MISS_KM = 1.0
DETECT_PC_THRESHOLD = 1e-7


def _event(miss_km: float, rel_speed_km_s: float) -> ConjunctionEvent:
    r_a = np.array([7000.0, 0.0, 0.0])
    v_a = np.array([0.0, 7.5, 0.0])
    r_b = np.array([7000.0, 0.0, miss_km])
    v_b = np.array([0.0, 7.5 + rel_speed_km_s, 0.0])
    return ConjunctionEvent(
        object_a=None, object_b=None, tca_s=3600.0, miss_distance_km=miss_km,
        rel_speed_km_s=rel_speed_km_s,
        r_a_km=r_a, v_a_km_s=v_a, r_b_km=r_b, v_b_km_s=v_b,
    )


def build_labelled_set() -> list[tuple[ConjunctionEvent, bool]]:
    cases: list[tuple[ConjunctionEvent, bool]] = []
    for miss in np.concatenate([np.linspace(0.05, 1.0, 12), np.linspace(1.5, 15.0, 14)]):
        for vrel in (0.5, 7.0, 14.0):
            cases.append((_event(float(miss), vrel), miss <= DANGEROUS_MISS_KM))
    return cases


def evaluate_false_negative_rate(model: RiskModel) -> tuple[float, int]:
    cases = build_labelled_set()
    RiskAssessor(model, window_hours=48.0).assess([c[0] for c in cases])
    dangerous = [ev for ev, is_dang in cases if is_dang]
    missed = [ev for ev in dangerous if (ev.pc or 0.0) < DETECT_PC_THRESHOLD]
    return len(missed) / len(dangerous), len(cases)
