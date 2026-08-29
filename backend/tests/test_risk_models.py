"""FosterEstesModel: monotonicity, high-recall, and a labelled synthetic set
that produces the false-negative-rate metric surfaced on /metrics."""
import numpy as np
import pytest

from app.domain import ConjunctionEvent
from app.services.assess import RiskAssessor
from app.services.metrics_store import metrics
from app.services.risk_models import FosterEstesModel


def event_with_miss(miss_km: float, rel_speed_km_s: float = 10.0,
                    tca_s: float = 3600.0) -> ConjunctionEvent:
    """Two objects on near-parallel tracks, offset by ``miss_km`` along the
    cross-track (z) axis; relative velocity is purely along-track (y)."""
    r_a = np.array([7000.0, 0.0, 0.0])
    v_a = np.array([0.0, 7.5, 0.0])
    r_b = np.array([7000.0, 0.0, miss_km])
    v_b = np.array([0.0, 7.5 + rel_speed_km_s, 0.0])
    return ConjunctionEvent(
        object_a=None, object_b=None, tca_s=tca_s, miss_distance_km=miss_km,
        rel_speed_km_s=rel_speed_km_s,
        r_a_km=r_a, v_a_km_s=v_a, r_b_km=r_b, v_b_km_s=v_b,
    )


def test_pc_is_monotonic_in_miss_distance():
    model = FosterEstesModel(intrack_growth_m_per_hour=0.0)
    misses = [0.05, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    pcs = [model.collision_probability(event_with_miss(m)) for m in misses]
    assert all(earlier >= later - 1e-12 for earlier, later in zip(pcs, pcs[1:])), pcs
    assert pcs[0] > pcs[-1]


def test_pc_bounded_between_0_and_1():
    model = FosterEstesModel()
    assert 0.0 <= model.collision_probability(event_with_miss(0.0)) <= 1.0
    assert model.collision_probability(event_with_miss(500.0)) < 1e-6


def test_direct_hit_has_high_pc():
    model = FosterEstesModel(hard_body_radius_m=50.0, intrack_growth_m_per_hour=0.0)
    pc = model.collision_probability(event_with_miss(0.0))
    assert pc > 1e-3


def test_high_recall_never_silently_drops_a_dangerous_case():
    """Synthetic labelled set: 'dangerous' == miss <= 1 km. Every dangerous case
    must score above the medium risk threshold. False positives are fine."""
    model = FosterEstesModel()
    assessor = RiskAssessor(model, window_hours=48.0)

    cases = []
    for miss in np.concatenate([np.linspace(0.05, 1.0, 12), np.linspace(1.5, 15.0, 14)]):
        for vrel in (0.5, 7.0, 14.0):
            ev = event_with_miss(float(miss), rel_speed_km_s=vrel)
            cases.append((ev, miss <= 1.0))

    assessor.assess([c[0] for c in cases])

    dangerous = [ev for ev, is_dang in cases if is_dang]
    missed = [ev for ev in dangerous if (ev.pc or 0.0) < model_threshold()]
    fn_rate = len(missed) / len(dangerous)
    metrics.record_false_negative_rate(fn_rate, len(cases))

    assert fn_rate == 0.0, f"false negatives: {[e.miss_distance_km for e in missed]}"


def model_threshold() -> float:
    return 1e-6
