"""Trajectory data for the 2-D separation plot and the 3-D globe. Reads the
cached coarse ephemerides from the last detection run - no re-propagation."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from app.container import get_container

router = APIRouter()


def _find_event(cid: str):
    container = get_container()
    result = container.get_detection(container.settings.default_window_hours)
    event = next((e for e in result.events if e.pair_id == cid), None)
    if event is None:
        raise HTTPException(404, f"unknown conjunction_id '{cid}'")
    return result, event


@router.get("/conjunctions/{conjunction_id}/separation")
def separation_timeline(conjunction_id: str) -> dict:
    result, event = _find_event(conjunction_id)
    a, b = event.object_a, event.object_b
    t = result.times_s
    sep = np.linalg.norm(a.ephemeris.r_km - b.ephemeris.r_km, axis=1)
    # Trim to a readable window around TCA.
    tca_h = event.tca_s / 3600.0
    hours = t / 3600.0
    mask = np.abs(hours - tca_h) <= 6.0
    if mask.sum() < 5:
        mask = np.ones_like(hours, dtype=bool)
    return {
        "conjunction_id": conjunction_id,
        "object_a": {"norad_id": a.norad_id, "name": a.name},
        "object_b": {"norad_id": b.norad_id, "name": b.name},
        "tca_hours": round(tca_h, 3),
        "miss_distance_km": round(event.miss_distance_km, 4),
        "times_hours": [round(float(x), 4) for x in hours[mask]],
        "separation_km": [round(float(x), 3) for x in sep[mask]],
    }


@router.get("/conjunctions/{conjunction_id}/geometry")
def orbit_geometry(conjunction_id: str, points: int = 240) -> dict:
    result, event = _find_event(conjunction_id)
    t = result.times_s
    step = max(1, len(t) // max(points, 1))
    idx = np.arange(0, len(t), step)

    def path(obj):
        return [[round(float(c), 2) for c in obj.ephemeris.r_km[i]] for i in idx]

    tca_i = int(np.argmin(np.abs(t - event.tca_s)))
    return {
        "conjunction_id": conjunction_id,
        "epoch": result.epoch_iso,
        "times_hours": [round(float(t[i] / 3600.0), 4) for i in idx],
        "object_a": {
            "norad_id": event.object_a.norad_id, "name": event.object_a.name,
            "path_km": path(event.object_a),
        },
        "object_b": {
            "norad_id": event.object_b.norad_id, "name": event.object_b.name,
            "path_km": path(event.object_b),
        },
        "tca_index": int(np.searchsorted(idx, tca_i)),
        "tca_point_a_km": [round(float(c), 2) for c in event.r_a_km],
        "tca_point_b_km": [round(float(c), 2) for c in event.r_b_km],
    }
