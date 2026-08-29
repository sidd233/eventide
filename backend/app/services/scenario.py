"""Synthetic conjunction injection for demos and tests.

The live catalog rarely contains a sub-kilometre, high-Pc conjunction inside a
48-hour window, so the maneuver-rejection showcase needs a guaranteed scenario.
This builds a fake debris TLE by perturbing a real satellite's orbit plane and
phase until the two pass within a target miss distance, then exposes it through
a :class:`TLESource` decorator. Every conjunction involving the injected NORAD id
is flagged ``synthetic: true`` in the API so it is never mistaken for real data.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sgp4.api import Satrec

from app.domain import TLE
from app.interfaces.tle_source import TLESource

SYNTHETIC_NORAD_ID = 99001


def _checksum(line68: str) -> int:
    total = 0
    for ch in line68[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10


def _fmt_line2(
    norad: int, inc: float, raan: float, ecc: float, argp: float, ma: float,
    mean_motion: float, rev: int,
) -> str:
    ecc_str = f"{ecc:.7f}"[2:]
    body = (
        f"2 {norad:05d} {inc:8.4f} {raan:8.4f} {ecc_str} {argp:8.4f} "
        f"{ma:8.4f} {mean_motion:11.8f}{rev:5d}"
    )
    return body + str(_checksum(body))


def _fmt_line1(norad: int, epoch: str) -> str:
    body = (
        f"1 {norad:05d}U 99001A   {epoch}  .00000000  00000-0  00000-0 0  999"
    )
    return body + str(_checksum(body))


@dataclass
class InjectedScenario:
    tle: TLE
    target_norad: int
    miss_distance_km: float
    tca_hours: float


def _separation_at(sat_a: Satrec, sat_b: Satrec, jd: float, fr: np.ndarray) -> np.ndarray:
    _, ra, _ = sat_a.sgp4_array(np.full_like(fr, jd), fr)
    _, rb, _ = sat_b.sgp4_array(np.full_like(fr, jd), fr)
    return np.linalg.norm(np.asarray(ra) - np.asarray(rb), axis=1)


def _min_separation(sat_a: Satrec, sat_b: Satrec, jd: float, fr: np.ndarray) -> tuple[float, float]:
    """Minimum separation over ``fr``, with successive time refinement so a
    fast (multi-km/s) pass is not stepped over by the coarse grid."""
    d = _separation_at(sat_a, sat_b, jd, fr)
    k = int(np.argmin(d))
    lo = float(fr[max(0, k - 2)])
    hi = float(fr[min(len(fr) - 1, k + 2)])
    best_fr, best_d = float(fr[k]), float(d[k])
    for _ in range(4):
        fine = np.linspace(lo, hi, 200)
        df = _separation_at(sat_a, sat_b, jd, fine)
        kf = int(np.argmin(df))
        best_fr, best_d = float(fine[kf]), float(df[kf])
        step = fine[1] - fine[0]
        lo, hi = best_fr - 2 * step, best_fr + 2 * step
    return best_d, best_fr


def build_conjunction_scenario(
    target: TLE,
    window_hours: float = 48.0,
    target_miss_km: float = 0.3,
    norad_id: int = SYNTHETIC_NORAD_ID,
    inclination_offset_deg: float = 70.0,
) -> InjectedScenario:
    """Craft a debris TLE on a genuine crossing trajectory with ``target``.

    The synthetic object keeps the target's altitude (same mean motion and
    eccentricity) but is placed in a steeply different orbit plane, so the two
    cross at several km/s - a realistic high-energy conjunction. RAAN and mean
    anomaly are searched so the crossing lands inside the screening window with
    a usable lead time for an avoidance burn.
    """
    tsat = Satrec.twoline2rv(target.line1, target.line2)
    jd0 = tsat.jdsatepoch
    fr0 = tsat.jdsatepochF
    fr_grid = fr0 + np.linspace(6 / 24, window_hours / 24, 2400)

    epoch_str = target.line1[18:32]
    inc0 = float(target.line2[8:16])
    raan0 = float(target.line2[17:25])
    ecc0 = float("0." + target.line2[26:33])
    argp0 = float(target.line2[34:42])
    ma0 = float(target.line2[43:51])
    mm0 = float(target.line2[52:63])
    rev0 = int(target.line2[63:68])

    inc_syn = (inc0 + inclination_offset_deg) % 180.0

    def evaluate(raan: float, ma: float) -> tuple[float, float, TLE]:
        line1 = _fmt_line1(norad_id, epoch_str)
        line2 = _fmt_line2(
            norad_id, inc_syn, raan % 360.0, ecc0, argp0, ma % 360.0, mm0, rev0
        )
        cand = TLE(name="SYNTHETIC DEBRIS 99001", line1=line1, line2=line2)
        csat = Satrec.twoline2rv(line1, line2)
        miss, fr_tca = _min_separation(tsat, csat, jd0, fr_grid)
        return miss, (fr_tca - fr0) * 24.0, cand

    # 2-D search over RAAN and mean anomaly, coarse then local refinement.
    coarse = [
        evaluate(raan0 + dr, ma0 + dm)
        for dr in np.linspace(0.0, 360.0, 24, endpoint=False)
        for dm in np.linspace(0.0, 360.0, 36, endpoint=False)
    ]
    best = min(coarse, key=lambda x: x[0])
    b_raan = float(best[2].line2[17:25])
    b_ma = float(best[2].line2[43:51])

    span_r, span_m = 5.0, 2.5
    for _ in range(6):
        local = [
            evaluate(b_raan + dr, b_ma + dm)
            for dr in np.linspace(-span_r, span_r, 7)
            for dm in np.linspace(-span_m, span_m, 7)
        ]
        cand_best = min(local, key=lambda x: x[0])
        if cand_best[0] < best[0]:
            best = cand_best
            b_raan = float(best[2].line2[17:25])
            b_ma = float(best[2].line2[43:51])
        span_r *= 0.5
        span_m *= 0.5
        if best[0] <= target_miss_km:
            break

    miss, tca_hours, tle = best
    return InjectedScenario(
        tle=tle, target_norad=target.norad_id,
        miss_distance_km=miss, tca_hours=tca_hours,
    )


class ScenarioInjectingTLESource(TLESource):
    """Wraps another source and appends a synthetic collision-course object
    aimed at a chosen catalog satellite (default: the first station)."""

    def __init__(
        self,
        base: TLESource,
        window_hours: float = 48.0,
        target_name_hint: str | None = None,
        target_miss_km: float = 0.3,
    ):
        self._base = base
        self._window_hours = window_hours
        self._hint = target_name_hint
        self._target_miss_km = target_miss_km
        self._scenario: InjectedScenario | None = None

    @property
    def scenario(self) -> InjectedScenario | None:
        return self._scenario

    def _pick_target(self, tles: list[TLE]) -> TLE:
        if self._hint:
            for t in tles:
                if self._hint.lower() in t.name.lower():
                    return t
        # Prefer a well-known crewed / large object for a legible demo.
        for key in ("ISS (ZARYA)", "ISS", "CSS (TIANHE)", "TIANHE"):
            for t in tles:
                if key in t.name.upper():
                    return t
        return tles[0]

    def fetch(self) -> list[TLE]:
        tles = list(self._base.fetch())
        if self._scenario is None:
            target = self._pick_target(tles)
            self._scenario = build_conjunction_scenario(
                target, self._window_hours, self._target_miss_km
            )
        return tles + [self._scenario.tle]
