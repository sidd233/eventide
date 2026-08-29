"""Shared domain -> API mapping helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain import ConjunctionEvent, DetectionResult
from app.models import ConjunctionOut, ObjectRef
from app.services.scenario import SYNTHETIC_NORAD_ID


def event_to_out(ev: ConjunctionEvent, result: DetectionResult) -> ConjunctionOut:
    epoch = datetime.fromisoformat(result.epoch_iso)
    tca_dt = epoch + timedelta(seconds=ev.tca_s)
    return ConjunctionOut(
        conjunction_id=ev.pair_id,
        object_a=ObjectRef(norad_id=ev.object_a.norad_id, name=ev.object_a.name),
        object_b=ObjectRef(norad_id=ev.object_b.norad_id, name=ev.object_b.name),
        tca=tca_dt.isoformat(),
        tca_hours_from_now=round(ev.tca_s / 3600.0, 3),
        miss_distance_km=round(ev.miss_distance_km, 4),
        rel_speed_km_s=round(ev.rel_speed_km_s, 4),
        pc=ev.pc,
        risk_score=ev.risk_score,
        risk_tier=ev.risk_tier,
        synthetic=SYNTHETIC_NORAD_ID in (ev.object_a.norad_id, ev.object_b.norad_id),
    )
