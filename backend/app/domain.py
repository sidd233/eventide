"""Internal domain objects passed between services.

These are deliberately plain dataclasses (not pydantic) so the physics layer has
no web-framework dependency. API request/response shapes live in ``models.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class TLE:
    name: str
    line1: str
    line2: str

    @property
    def norad_id(self) -> int:
        return int(self.line1[2:7])


@dataclass
class Ephemeris:
    """A propagated trajectory in the TEME frame.

    ``times_s`` are seconds from the common epoch shared by every object in a
    screening run. ``r_km`` / ``v_km_s`` are (N, 3) arrays aligned with it.
    """

    times_s: np.ndarray
    r_km: np.ndarray
    v_km_s: np.ndarray

    def __len__(self) -> int:
        return int(self.times_s.shape[0])


@dataclass
class ScreeningObject:
    tle: TLE
    ephemeris: Ephemeris
    perigee_alt_km: float
    apogee_alt_km: float
    satrec: object = None            # cached sgp4 Satrec for on-demand refinement
    # Optional override: Callable[[float], tuple[r_km, v_km_s]] in run-epoch
    # seconds. When set it takes precedence over ``satrec`` (used by tests to
    # inject analytic trajectories without a TLE).
    state_provider: object = None

    @property
    def norad_id(self) -> int:
        return self.tle.norad_id

    @property
    def name(self) -> str:
        return self.tle.name.strip()


@dataclass
class ConjunctionEvent:
    object_a: ScreeningObject
    object_b: ScreeningObject
    tca_s: float                 # seconds from the run epoch
    miss_distance_km: float
    rel_speed_km_s: float
    r_a_km: np.ndarray           # position of A at TCA (TEME)
    r_b_km: np.ndarray
    v_a_km_s: np.ndarray
    v_b_km_s: np.ndarray

    # Filled in by the assessment stage.
    pc: float | None = None
    risk_score: float | None = None
    risk_tier: str | None = None

    @property
    def pair_id(self) -> str:
        lo, hi = sorted((self.object_a.norad_id, self.object_b.norad_id))
        return f"{lo}-{hi}"


@dataclass
class DetectionResult:
    events: list[ConjunctionEvent]
    epoch_iso: str
    window_hours: float
    object_count: int
    pairs_before_filter: int
    pairs_after_filter: int
    screening_latency_s: float

    # Runtime handles needed by maneuver re-screening (not serialised).
    objects: list["ScreeningObject"] = field(default_factory=list)
    times_s: "np.ndarray | None" = None
    epoch_jd: float = 0.0
    epoch_fr: float = 0.0

    @property
    def reduction_rate(self) -> float:
        if self.pairs_before_filter == 0:
            return 0.0
        return 1.0 - self.pairs_after_filter / self.pairs_before_filter


@dataclass
class ManeuverCandidate:
    dv_rtn_mps: tuple[float, float, float]
    dv_magnitude_mps: float
    burn_time_s: float
    accepted: bool = False
    rejection_reason: str | None = None
    residual_pc: float | None = None          # Pc of the original conjunction after the burn
    new_conjunctions: list[dict] = field(default_factory=list)
    timing_margin_hours: float | None = None
