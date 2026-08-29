"""Phase 1 integration: the detection pipeline over a fixed fixture catalog."""
import numpy as np

from app.services.detect import ConjunctionDetector
from app.services.filters import AcceptAllFilter, ApsisFilter
from app.services.tle_fetch import FileTLESource


def test_conjunctions_returns_sane_nonempty_result(fixture_tle_path):
    det = ConjunctionDetector(
        FileTLESource(fixture_tle_path), [ApsisFilter(15.0)],
        max_objects=120, coarse_step_s=60.0,
        refine_threshold_km=25.0, report_threshold_km=10.0,
    )
    res = det.screen(window_hours=48.0)

    assert res.object_count > 50
    assert res.pairs_before_filter > 0
    assert res.pairs_after_filter <= res.pairs_before_filter
    assert res.events, "expected the Cosmos-2251 debris cloud to yield conjunctions"
    for ev in res.events:
        assert 0.0 <= ev.miss_distance_km <= 10.0
        assert 0.0 <= ev.tca_s <= 48 * 3600 + 120
        assert ev.rel_speed_km_s >= 0.0
    misses = [e.miss_distance_km for e in res.events]
    assert misses == sorted(misses)


def test_apsis_filter_reduces_pair_count_vs_accept_all(fixture_tle_path):
    src = FileTLESource(fixture_tle_path)
    common = dict(max_objects=150, coarse_step_s=120.0,
                  refine_threshold_km=25.0, report_threshold_km=10.0)

    baseline = ConjunctionDetector(src, [AcceptAllFilter()], **common).screen(24.0)
    filtered = ConjunctionDetector(src, [ApsisFilter(15.0)], **common).screen(24.0)

    assert filtered.pairs_before_filter == baseline.pairs_before_filter
    assert filtered.pairs_after_filter < baseline.pairs_after_filter
    # Reduction rate should be a meaningful fraction. Literature (Stevenson 2023)
    # reports ~62% for a comparable altitude filter on a full catalog; this
    # fixture is dominated by a single-altitude debris cloud so a lower figure
    # is expected, but it must still cut a real chunk.
    assert filtered.reduction_rate > 0.15
    print(f"apsis reduction rate on fixture: {filtered.reduction_rate:.3f}")


def test_detector_is_deterministic_for_fixed_epoch(fixture_tle_path):
    from datetime import datetime, timezone

    det = ConjunctionDetector(
        FileTLESource(fixture_tle_path), [ApsisFilter(15.0)],
        max_objects=80, coarse_step_s=90.0,
    )
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = det.screen(24.0, when=when)
    b = det.screen(24.0, when=when)
    assert [e.pair_id for e in a.events] == [e.pair_id for e in b.events]
    assert np.allclose(
        [e.miss_distance_km for e in a.events],
        [e.miss_distance_km for e in b.events],
    )
