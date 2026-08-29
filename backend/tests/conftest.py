import numpy as np
import pytest

from app.domain import Ephemeris, ScreeningObject, TLE
from app.services.propagate import time_grid_s


def make_object(
    norad_id: int,
    perigee_alt_km: float,
    apogee_alt_km: float,
    *,
    times_s: np.ndarray | None = None,
    r_km: np.ndarray | None = None,
    v_km_s: np.ndarray | None = None,
    state_provider=None,
) -> ScreeningObject:
    """A ScreeningObject with hand-set orbital extent and (optionally) an
    analytic trajectory - no TLE / SGP4 needed. For filter and risk tests."""
    if times_s is None:
        times_s = time_grid_s(1.0, 60.0)
    n = len(times_s)
    if r_km is None:
        r_km = np.zeros((n, 3))
    if v_km_s is None:
        v_km_s = np.zeros((n, 3))
    line1 = f"1 {norad_id:05d}U 98067A   24001.00000000  .00000000  00000-0  00000-0 0  9990"
    line2 = f"2 {norad_id:05d}  51.6000 000.0000 0001000 000.0000 000.0000 15.50000000000000"
    return ScreeningObject(
        tle=TLE(name=f"OBJ-{norad_id}", line1=line1, line2=line2),
        ephemeris=Ephemeris(times_s, r_km, v_km_s),
        perigee_alt_km=perigee_alt_km,
        apogee_alt_km=apogee_alt_km,
        state_provider=state_provider,
    )


@pytest.fixture
def fixture_tle_path() -> str:
    import pathlib

    return str(pathlib.Path(__file__).parent / "fixtures" / "sample_tles.txt")


@pytest.fixture(scope="session")
def injected_detection():
    """Run the real detection pipeline over the fixture catalog plus one
    injected synthetic collision-course object aimed at the ISS. Returns
    ``(DetectionResult, synthetic_event)``."""
    from app.services.assess import RiskAssessor
    from app.services.detect import ConjunctionDetector
    from app.services.filters import ApsisFilter
    from app.services.risk_models import FosterEstesModel
    from app.services.scenario import SYNTHETIC_NORAD_ID, ScenarioInjectingTLESource
    from app.services.tle_fetch import FileTLESource
    import pathlib

    path = pathlib.Path(__file__).parent / "fixtures" / "sample_tles.txt"
    source = ScenarioInjectingTLESource(
        FileTLESource(path), window_hours=48.0, target_name_hint="ISS (ZARYA)"
    )
    detector = ConjunctionDetector(
        source, [ApsisFilter(15.0)], max_objects=120,
        coarse_step_s=60.0, refine_threshold_km=25.0, report_threshold_km=10.0,
    )
    result = detector.screen(48.0)
    RiskAssessor(FosterEstesModel(), window_hours=48.0).assess(result.events)
    synthetic = next(
        e for e in result.events
        if SYNTHETIC_NORAD_ID in (e.object_a.norad_id, e.object_b.norad_id)
    )
    return result, synthetic
