"""Time-of-closest-approach refinement, shared by detection and maneuver
re-screening. Single responsibility: given two trajectory callables and a time
bracket, find the local separation minimum."""
from __future__ import annotations

from typing import Callable

import numpy as np
from scipy.optimize import minimize_scalar

StateFn = Callable[[float], tuple[np.ndarray, np.ndarray]]


def segment_closest_approach(dr: np.ndarray) -> np.ndarray:
    """Given relative-position samples ``dr`` of shape ``(..., T, 3)``, return
    the closest distance to zero of each straight segment between consecutive
    samples, shape ``(..., T-1)``.

    This does not miss a fast (multi-km/s) conjunction the way a plain
    per-sample minimum does: even when both endpoints of a segment are hundreds
    of km apart, the segment itself may pass within metres of zero.
    """
    d0 = dr[..., :-1, :]
    seg = dr[..., 1:, :] - d0
    denom = np.sum(seg * seg, axis=-1)
    num = -np.sum(d0 * seg, axis=-1)
    frac = np.clip(
        np.divide(num, denom, out=np.zeros_like(num), where=denom > 0), 0.0, 1.0
    )
    closest = d0 + frac[..., None] * seg
    return np.linalg.norm(closest, axis=-1)


def refine_tca(
    state_a: StateFn, state_b: StateFn, t_lo: float, t_hi: float
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    def sep(t: float) -> float:
        ra, _ = state_a(t)
        rb, _ = state_b(t)
        return float(np.linalg.norm(ra - rb))

    res = minimize_scalar(sep, bounds=(t_lo, t_hi), method="bounded",
                          options={"xatol": 1e-3})
    tca = float(res.x)
    ra, va = state_a(tca)
    rb, vb = state_b(tca)
    miss = float(np.linalg.norm(ra - rb))
    return tca, miss, np.asarray(ra), np.asarray(va), np.asarray(rb), np.asarray(vb)


def sgp4_state_fn(sat, epoch_jd: float, epoch_fr: float) -> StateFn:
    def fn(t_s: float) -> tuple[np.ndarray, np.ndarray]:
        _, r, v = sat.sgp4(epoch_jd, epoch_fr + t_s / 86400.0)
        return np.array(r), np.array(v)

    return fn


def object_states(obj, times_s: np.ndarray, epoch_jd: float, epoch_fr: float):
    """Vectorised (R, V) arrays for a ScreeningObject over ``times_s``."""
    if obj.state_provider is not None:
        rv = [obj.state_provider(float(t)) for t in times_s]
        return np.array([x[0] for x in rv]), np.array([x[1] for x in rv])
    jd = np.full(np.shape(times_s), epoch_jd, dtype=float)
    fr = epoch_fr + np.asarray(times_s, dtype=float) / 86400.0
    _, r, v = obj.satrec.sgp4_array(jd, fr)
    return np.asarray(r), np.asarray(v)


def object_state_fn(obj, epoch_jd: float, epoch_fr: float) -> StateFn:
    """Trajectory callable for a :class:`ScreeningObject`: its injected
    ``state_provider`` if present, otherwise SGP4 via its cached Satrec."""
    if obj.state_provider is not None:
        return obj.state_provider
    return sgp4_state_fn(obj.satrec, epoch_jd, epoch_fr)
