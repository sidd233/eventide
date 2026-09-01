"""Composition root. Builds and wires the concrete implementations behind the
abstractions the services depend on. This is the *only* place that names
concrete classes like ``CelesTrakTLESource`` or ``FosterEstesModel``.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from pathlib import Path

from app.config import Settings, get_settings
from app.domain import DetectionResult
from app.services.assess import RiskAssessor
from app.services.detect import ConjunctionDetector
from app.services.filters import ApsisFilter
from app.services.maneuver import ManeuverGenerator, ManeuverPlanner
from app.services.risk_models import FosterEstesModel
from app.services.scenario import SYNTHETIC_NORAD_ID, ScenarioInjectingTLESource
from app.services.tle_fetch import CelesTrakTLESource


class Container:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        s = self.settings

        bootstrap = Path(__file__).parent / "data" / "bootstrap_tles.txt"
        self.tle_source = CelesTrakTLESource(
            groups=s.tle_groups,
            ttl_s=s.tle_cache_ttl_s,
            timeout_s=s.tle_timeout_s,
            bootstrap_path=bootstrap if bootstrap.is_file() else None,
        )
        self.scenario_source: ScenarioInjectingTLESource | None = None
        if s.demo_inject_scenario:
            self.scenario_source = ScenarioInjectingTLESource(
                self.tle_source,
                window_hours=s.default_window_hours,
                target_name_hint=s.demo_target_hint,
            )
        active_source = self.scenario_source or self.tle_source
        self.detector = ConjunctionDetector(
            tle_source=active_source,
            filters=[ApsisFilter(pad_km=s.apsis_pad_km)],
            max_objects=s.max_objects,
            coarse_step_s=s.coarse_step_s,
            refine_threshold_km=s.refine_threshold_km,
            report_threshold_km=s.report_threshold_km,
        )
        self.risk_model = FosterEstesModel(
            sigma_rtn_m=(s.sigma_radial_m, s.sigma_intrack_m, s.sigma_crosstrack_m),
            hard_body_radius_m=s.hard_body_radius_m,
            intrack_growth_m_per_hour=s.intrack_growth_m_per_hour,
        )
        self.assessor = RiskAssessor(
            self.risk_model,
            pc_high=s.pc_high,
            pc_medium=s.pc_medium,
            window_hours=s.default_window_hours,
        )
        self.maneuver_generator = ManeuverGenerator(
            dv_grid_mps=s.maneuver_dv_grid_mps, lead_hours=s.maneuver_lead_hours
        )
        self.maneuver_planner = ManeuverPlanner(
            self.risk_model,
            pc_reject=s.maneuver_pc_reject,
            report_threshold_km=s.report_threshold_km,
            refine_threshold_km=s.refine_threshold_km,
            coarse_step_s=s.coarse_step_s,
        )

        self._lock = threading.Lock()
        # Bounded LRU: each entry retains a full DetectionResult (every object's
        # coarse ephemeris + Satrec, tens of MB). window_hours is a free-form
        # query parameter, so an unbounded dict here is a memory leak - a client
        # sweeping the window would pin one large result per distinct value.
        self._cache: OrderedDict[float, tuple[float, DetectionResult]] = OrderedDict()
        self._cache_ttl_s = 300.0
        self._cache_max = s.detection_cache_size

    def get_detection(self, window_hours: float, *, force: bool = False) -> DetectionResult:
        with self._lock:
            hit = self._cache.get(window_hours)
            if hit and not force and time.monotonic() - hit[0] < self._cache_ttl_s:
                self._cache.move_to_end(window_hours)
                return hit[1]
        result = self.detector.screen(window_hours)
        self.assessor.assess(result.events)
        with self._lock:
            self._cache[window_hours] = (time.monotonic(), result)
            self._cache.move_to_end(window_hours)
            while len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)
        return result


_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container()
    return _container
