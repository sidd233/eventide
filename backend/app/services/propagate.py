"""SGP4 propagation wrapper.

Single responsibility: turn a TLE (or a raw state vector, for post-maneuver
trajectories) into an :class:`Ephemeris` sampled on a caller-supplied time grid.
Nothing here knows about conjunctions, risk, or HTTP.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import numpy as np
from sgp4.api import Satrec, jday

from app.domain import Ephemeris, TLE

MU_EARTH_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137


def run_epoch_jd(when: datetime | None = None) -> tuple[float, float]:
    """Return ``(jd, fr)`` for the common epoch of a screening run (default: now)."""
    when = when or datetime.now(timezone.utc)
    return jday(
        when.year, when.month, when.day, when.hour, when.minute,
        when.second + when.microsecond * 1e-6,
    )


def time_grid_s(window_hours: float, step_s: float) -> np.ndarray:
    n = int(round(window_hours * 3600.0 / step_s)) + 1
    return np.arange(n, dtype=float) * step_s


class Propagator(ABC):
    """Propagates a single TLE onto an absolute time grid."""

    @abstractmethod
    def propagate(self, tle: TLE, times_s: np.ndarray, epoch_jd: float, epoch_fr: float) -> Ephemeris:
        raise NotImplementedError


class SGP4Propagator(Propagator):
    def propagate(self, tle: TLE, times_s: np.ndarray, epoch_jd: float, epoch_fr: float) -> Ephemeris:
        sat = Satrec.twoline2rv(tle.line1, tle.line2)
        # Spread the seconds offset across jd/fr keeping fr small for precision.
        days = times_s / 86400.0
        jd = np.full(times_s.shape, epoch_jd, dtype=float)
        fr = epoch_fr + days
        err, r, v = sat.sgp4_array(jd, fr)
        r = np.asarray(r, dtype=float)
        v = np.asarray(v, dtype=float)
        bad = np.asarray(err, dtype=int) != 0
        if bad.any():
            r[bad] = np.nan
            v[bad] = np.nan
        return Ephemeris(times_s=np.asarray(times_s, dtype=float), r_km=r, v_km_s=v)

    def states_at_minutes(self, tle: TLE, minutes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Propagate relative to the TLE's own epoch. Used for SGP4 verification
        against published test vectors expressed in minutes-since-epoch."""
        sat = Satrec.twoline2rv(tle.line1, tle.line2)
        jd = np.full(np.shape(minutes), sat.jdsatepoch, dtype=float)
        fr = sat.jdsatepochF + np.asarray(minutes, dtype=float) / 1440.0
        err, r, v = sat.sgp4_array(jd, fr)
        return np.asarray(r, dtype=float), np.asarray(v, dtype=float)


def apsis_altitudes_km(tle: TLE) -> tuple[float, float]:
    """Perigee and apogee altitude (km) from the mean motion and eccentricity in
    the TLE. Used by the APSIS prefilter."""
    sat = Satrec.twoline2rv(tle.line1, tle.line2)
    n_rad_s = sat.no_kozai / 60.0                      # rad/min -> rad/s
    a_km = (MU_EARTH_KM3_S2 / n_rad_s**2) ** (1.0 / 3.0)
    e = sat.ecco
    perigee = a_km * (1.0 - e) - EARTH_RADIUS_KM
    apogee = a_km * (1.0 + e) - EARTH_RADIUS_KM
    return perigee, apogee


class TwoBodyPropagator:
    """Keplerian two-body propagation from a raw state vector.

    Deliberately *not* a :class:`Propagator` subclass: it is seeded by a state,
    not a TLE. Used only for a maneuvered object's post-burn arc, where re-fitting
    an SGP4 mean element set would be overkill for an MVP. This mixed-propagator
    approximation is documented in the README as a modelling limitation.
    """

    def propagate_state(
        self, r0_km: np.ndarray, v0_km_s: np.ndarray, t0_s: float, times_s: np.ndarray
    ) -> Ephemeris:
        r0 = np.asarray(r0_km, dtype=float)
        v0 = np.asarray(v0_km_s, dtype=float)
        out_r = np.empty((len(times_s), 3))
        out_v = np.empty((len(times_s), 3))
        for i, t in enumerate(times_s):
            out_r[i], out_v[i] = _kepler_propagate(r0, v0, float(t) - t0_s)
        return Ephemeris(times_s=np.asarray(times_s, dtype=float), r_km=out_r, v_km_s=out_v)


def _kepler_propagate(r0: np.ndarray, v0: np.ndarray, dt_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Universal-variable two-body propagation (Vallado, Algorithm 8)."""
    mu = MU_EARTH_KM3_S2
    if dt_s == 0.0:
        return r0.copy(), v0.copy()
    r0n = np.linalg.norm(r0)
    v0n = np.linalg.norm(v0)
    alpha = -v0n**2 / mu + 2.0 / r0n            # 1/a
    sqrt_mu = np.sqrt(mu)
    rv0 = np.dot(r0, v0)

    # Initial guess for the universal anomaly chi.
    if alpha > 1e-12:                            # ellipse
        chi = sqrt_mu * dt_s * alpha
    elif abs(alpha) < 1e-12:                     # parabola
        h = np.cross(r0, v0)
        p = np.dot(h, h) / mu
        chi = sqrt_mu * dt_s / max(p, 1e-9)
    else:                                        # hyperbola
        a = 1.0 / alpha
        chi = np.sign(dt_s) * np.sqrt(-a) * np.log(
            -2.0 * mu * alpha * dt_s
            / (rv0 + np.sign(dt_s) * np.sqrt(-mu * a) * (1.0 - r0n * alpha))
        )

    for _ in range(100):
        psi = chi * chi * alpha
        c2, c3 = _stumpff(psi)
        r = chi**2 * c2 + rv0 / sqrt_mu * chi * (1.0 - psi * c3) + r0n * (1.0 - psi * c2)
        chi_new = chi + (
            sqrt_mu * dt_s
            - chi**3 * c3
            - rv0 / sqrt_mu * chi**2 * c2
            - r0n * chi * (1.0 - psi * c3)
        ) / r
        if abs(chi_new - chi) < 1e-9:
            chi = chi_new
            break
        chi = chi_new

    psi = chi * chi * alpha
    c2, c3 = _stumpff(psi)
    f = 1.0 - chi**2 / r0n * c2
    g = dt_s - chi**3 / sqrt_mu * c3
    rvec = f * r0 + g * v0
    rn = np.linalg.norm(rvec)
    fdot = sqrt_mu / (rn * r0n) * chi * (psi * c3 - 1.0)
    gdot = 1.0 - chi**2 / rn * c2
    vvec = fdot * r0 + gdot * v0
    return rvec, vvec


def _stumpff(psi: float) -> tuple[float, float]:
    if psi > 1e-6:
        s = np.sqrt(psi)
        return (1.0 - np.cos(s)) / psi, (s - np.sin(s)) / s**3
    if psi < -1e-6:
        s = np.sqrt(-psi)
        return (1.0 - np.cosh(s)) / psi, (np.sinh(s) - s) / s**3
    return 0.5, 1.0 / 6.0
