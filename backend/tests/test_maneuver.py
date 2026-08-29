"""Phase 3 - the core differentiator. Tested harder than anything else.

Every test runs the real detection pipeline over the fixture catalog plus one
injected synthetic collision-course object, then exercises maneuver generation
and re-screening against that conjunction.
"""
import numpy as np
import pytest

from app.domain import Ephemeris, ManeuverCandidate, ScreeningObject, TLE
from app.services.maneuver import ManeuverGenerator, ManeuverPlanner
from app.services.risk_models import FosterEstesModel


@pytest.fixture
def planner():
    return ManeuverPlanner(
        FosterEstesModel(), pc_reject=1e-6, report_threshold_km=10.0,
        refine_threshold_km=25.0, coarse_step_s=60.0,
    )


def _target_secondary(result, event):
    a_syn = event.object_a.norad_id == 99001
    target = event.object_b if a_syn else event.object_a       # maneuver the real asset
    secondary = event.object_a if a_syn else event.object_b
    return target, secondary


def test_pipeline_produced_a_dangerous_synthetic_conjunction(injected_detection):
    _, event = injected_detection
    assert event.miss_distance_km < 2.0
    assert event.rel_speed_km_s > 5.0
    assert event.pc is not None and event.pc > 1e-6


def test_rescreen_rejects_a_null_maneuver(injected_detection, planner):
    """A zero Delta-v 'maneuver' cannot reduce the risk - re_screen must reject
    it, and the reason must cite residual Pc."""
    result, event = injected_detection
    target, secondary = _target_secondary(result, event)

    null = ManeuverCandidate(dv_rtn_mps=(0.0, 0.0, 0.0), dv_magnitude_mps=0.0,
                             burn_time_s=max(0.0, event.tca_s - 12 * 3600))
    planner.re_screen(
        target, secondary, null, result.objects, result.times_s,
        result.epoch_jd, result.epoch_fr, baseline_pc=event.pc,
    )
    assert null.accepted is False
    assert "residual Pc" in (null.rejection_reason or "")
    assert null.residual_pc == pytest.approx(event.pc, rel=0.5)


def test_rescreen_accepts_a_clearly_safe_maneuver(injected_detection, planner):
    """A large along-track burn well before TCA moves the asset kilometres
    clear - re_screen must accept it (or, at worst, reject only because it
    created a brand-new conjunction, never because residual risk stayed high)."""
    result, event = injected_detection
    target, secondary = _target_secondary(result, event)

    burn = ManeuverCandidate(dv_rtn_mps=(0.0, 2.0, 0.0), dv_magnitude_mps=2.0,
                             burn_time_s=max(0.0, event.tca_s - 12 * 3600))
    planner.re_screen(
        target, secondary, burn, result.objects, result.times_s,
        result.epoch_jd, result.epoch_fr, baseline_pc=event.pc,
    )
    assert burn.residual_pc is not None and burn.residual_pc < 1e-6
    if not burn.accepted:
        assert burn.new_conjunctions, burn.rejection_reason


def test_rescreen_rejects_a_maneuver_that_creates_a_new_conjunction(
    injected_detection, planner
):
    """Put a third object exactly on the maneuvered asset's post-burn path.
    The burn clears the original conjunction but the re-screen must catch the
    new one and reject the candidate for it."""
    result, event = injected_detection
    target, secondary = _target_secondary(result, event)

    candidate = ManeuverCandidate(dv_rtn_mps=(0.0, 1.5, 0.0), dv_magnitude_mps=1.5,
                                  burn_time_s=max(0.0, event.tca_s - 12 * 3600))

    # Analytic post-burn trajectory of the asset for this exact candidate.
    *_, post_burn = planner.post_burn_state_fn(
        target, candidate, result.epoch_jd, result.epoch_fr
    )
    times = result.times_s
    t_enc = float(event.tca_s)          # make the shadow meet the post-burn asset here

    def shadow_provider(t: float):
        r, v = post_burn(t)
        # Far from the asset everywhere except a smooth approach to t_enc, so it
        # is genuinely a NEW conjunction, not a pre-existing co-orbiting object.
        gap = abs(t - t_enc) / 1800.0
        offset = np.array([600.0, 0.0, 0.0]) * min(gap, 1.0) ** 2
        return r + offset, v + np.array([0.0, 0.0, 3.0])   # crossing relative velocity

    shadow_r = np.array([shadow_provider(float(t))[0] for t in times])
    shadow_v = np.array([shadow_provider(float(t))[1] for t in times])
    shadow = ScreeningObject(
        tle=TLE(
            name="SHADOW-DEBRIS",
            line1="1 90909U 24001A   24001.00000000  .00000000  00000-0  00000-0 0  9990",
            line2="2 90909  51.6000 000.0000 0001000 000.0000 000.0000 15.50000000000000",
        ),
        ephemeris=Ephemeris(times, shadow_r, shadow_v),
        perigee_alt_km=300.0, apogee_alt_km=500.0,
        state_provider=shadow_provider,    # meets the post-burn asset at t_enc
    )
    assert shadow.norad_id == 90909
    catalog = list(result.objects) + [shadow]

    planner.re_screen(
        target, secondary, candidate, catalog, times,
        result.epoch_jd, result.epoch_fr, baseline_pc=event.pc,
    )
    assert candidate.accepted is False
    assert candidate.new_conjunctions
    assert "new conjunction" in (candidate.rejection_reason or "")


def test_recommend_ranks_survivors_and_reports_rejection_rate(injected_detection):
    result, event = injected_detection
    target, secondary = _target_secondary(result, event)

    generator = ManeuverGenerator(dv_grid_mps=[0.05, 0.2, 1.0], lead_hours=12.0)
    planner = ManeuverPlanner(FosterEstesModel(), pc_reject=1e-6)
    candidates = generator.generate(event)
    assert len(candidates) == 6 * 3

    accepted, stats = planner.recommend(
        target, secondary, candidates, result.objects, result.times_s,
        result.epoch_jd, result.epoch_fr, baseline_pc=event.pc,
    )
    assert stats["candidates_generated"] == 18
    assert 0.0 <= stats["rejection_rate"] <= 1.0
    assert stats["rescreen_s_per_candidate"] is not None
    # Survivors ranked by residual Pc ascending.
    residuals = [c.residual_pc or 0.0 for c in accepted]
    assert residuals == sorted(residuals)
    # At least one big burn should be safe.
    assert accepted, "expected at least one safe maneuver among the grid"
