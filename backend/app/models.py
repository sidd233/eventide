"""Pydantic request/response schemas for the HTTP layer."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "eventide"
    tle_source_error: str | None = None
    tle_served_stale: bool = False


class ObjectRef(BaseModel):
    norad_id: int
    name: str


class ConjunctionOut(BaseModel):
    conjunction_id: str
    object_a: ObjectRef
    object_b: ObjectRef
    tca: str                       # ISO 8601 UTC
    tca_hours_from_now: float
    miss_distance_km: float
    rel_speed_km_s: float
    pc: float | None = None
    risk_score: float | None = None
    risk_tier: str | None = None
    synthetic: bool = False        # true if this involves the injected demo object


class ConjunctionsResponse(BaseModel):
    epoch: str
    window_hours: float
    object_count: int
    pairs_before_filter: int
    pairs_after_filter: int
    prefilter_reduction_rate: float
    screening_latency_s: float
    conjunctions: list[ConjunctionOut]


class ManeuverRequest(BaseModel):
    object_id: int = Field(..., description="NORAD id of the object to maneuver (must be a member of the conjunction pair)")
    conjunction_id: str


class ManeuverOut(BaseModel):
    dv_rtn_mps: list[float]
    dv_magnitude_mps: float
    burn_time: str
    timing_margin_hours: float | None
    accepted: bool
    rejection_reason: str | None
    residual_pc: float | None
    new_conjunctions: list[dict]


class ManeuverResponse(BaseModel):
    conjunction_id: str
    maneuvered_object: ObjectRef
    secondary_object: ObjectRef
    baseline_pc: float
    baseline_miss_distance_km: float
    candidates_generated: int
    candidates_rejected: int
    rejection_rate: float | None
    rescreen_s_per_candidate: float | None
    recommended: list[ManeuverOut]
    rejected: list[ManeuverOut]
    message: str
