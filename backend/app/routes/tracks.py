"""Trajectory data for the 2-D separation plot and the 3-D globe. Reads the
cached coarse ephemerides from the last detection run - no re-propagation."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from app.container import get_container
from app.services.tca import object_states

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
    t = np.asarray(result.times_s, dtype=float)
    tca_h = event.tca_s / 3600.0

    # Trim to a readable window around TCA.
    mask = np.abs(t / 3600.0 - tca_h) <= 6.0
    if mask.sum() < 5:
        mask = np.ones_like(t, dtype=bool)

    sep = np.linalg.norm(a.ephemeris.r_km - b.ephemeris.r_km, axis=1)
    coarse_t = t[mask]
    coarse_sep = sep[mask]

    # The encounter itself is a sharp V that the 60 s screening grid steps over:
    # at ~10-15 km/s relative speed the separation falls thousands of km per
    # minute near TCA, so the nearest coarse samples sit hundreds of km above the
    # true (refined) miss distance and the TCA marker looks disconnected from the
    # curve. Splice a 1 s grid across +-3 min of TCA so the plotted line actually
    # reaches the closest approach.
    near = np.abs(coarse_t - event.tca_s) <= 180.0
    merged_t, merged_sep = coarse_t[~near], coarse_sep[~near]

    lo = max(float(t[0]), event.tca_s - 180.0)
    hi = min(float(t[-1]), event.tca_s + 180.0)
    dense_t = np.arange(lo, hi + 1e-6, 1.0)
    if dense_t.size:
        ra, _ = object_states(a, dense_t, result.epoch_jd, result.epoch_fr)
        rb, _ = object_states(b, dense_t, result.epoch_jd, result.epoch_fr)
        dense_sep = np.linalg.norm(np.asarray(ra) - np.asarray(rb), axis=1)
        merged_t = np.concatenate([merged_t, dense_t])
        merged_sep = np.concatenate([merged_sep, dense_sep])

    order = np.argsort(merged_t)
    merged_t, merged_sep = merged_t[order], merged_sep[order]

    return {
        "conjunction_id": conjunction_id,
        "object_a": {"norad_id": a.norad_id, "name": a.name},
        "object_b": {"norad_id": b.norad_id, "name": b.name},
        "tca_hours": round(tca_h, 6),
        "miss_distance_km": round(event.miss_distance_km, 4),
        "times_hours": [round(float(x) / 3600.0, 6) for x in merged_t],
        "separation_km": [round(float(x), 3) for x in merged_sep],
    }


@router.get("/conjunctions/{conjunction_id}/geometry")
def orbit_geometry(conjunction_id: str, window_min: float = 90.0) -> dict:
    """Trajectory samples for the animated 3-D encounter view.

    Trimmed to +-``window_min`` around TCA (roughly one revolution each side) so
    the globe shows the close approach rather than 30 overlaid orbits, and
    re-propagated on a fine grid with a 1 s patch through TCA so the animated
    markers actually reach the miss distance.
    """
    result, event = _find_event(conjunction_id)
    a, b = event.object_a, event.object_b
    t = np.asarray(result.times_s, dtype=float)
    tca = float(event.tca_s)

    lo = max(float(t[0]), tca - window_min * 60.0)
    hi = min(float(t[-1]), tca + window_min * 60.0)

    grid = np.arange(lo, hi + 1e-6, 15.0)
    fine = np.arange(max(lo, tca - 150.0), min(hi, tca + 150.0) + 1e-6, 1.0)
    times = np.unique(np.concatenate([grid, fine, [tca]]))
    times = times[(times >= lo) & (times <= hi)]

    ra, _ = object_states(a, times, result.epoch_jd, result.epoch_fr)
    rb, _ = object_states(b, times, result.epoch_jd, result.epoch_fr)
    ra, rb = np.asarray(ra), np.asarray(rb)

    tca_i = int(np.argmin(np.abs(times - tca)))

    def path(r):
        return [[round(float(c), 3) for c in p] for p in r]

    return {
        "conjunction_id": conjunction_id,
        "epoch": result.epoch_iso,
        "window_min": window_min,
        "times_s": [round(float(x), 3) for x in times],
        "tca_s": round(tca, 3),
        "tca_index": tca_i,
        "miss_distance_km": round(event.miss_distance_km, 4),
        "object_a": {
            "norad_id": a.norad_id, "name": a.name, "path_km": path(ra),
        },
        "object_b": {
            "norad_id": b.norad_id, "name": b.name, "path_km": path(rb),
        },
        "tca_point_a_km": [round(float(c), 3) for c in ra[tca_i]],
        "tca_point_b_km": [round(float(c), 3) for c in rb[tca_i]],
    }
