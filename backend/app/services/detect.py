"""Conjunction detection pipeline orchestrator.

fetch TLEs -> propagate onto a coarse grid -> prefilter pairs -> coarse
minimum-separation scan -> refine TCA & miss distance for survivors.

Depends only on the :class:`TLESource` and :class:`ConjunctionFilter`
abstractions plus a :class:`Propagator`, all injected at construction. That is
what lets the integration tests run against a fixed fixture set instead of the
live CelesTrak API.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np

from app.domain import (
    ConjunctionEvent,
    DetectionResult,
    Ephemeris,
    ScreeningObject,
    TLE,
)
from app.interfaces.conjunction_filter import ConjunctionFilter
from app.interfaces.tle_source import TLESource
from app.services.propagate import (
    SGP4Propagator,
    apsis_altitudes_km,
    run_epoch_jd,
    time_grid_s,
)
from app.services.tca import refine_tca, segment_closest_approach, sgp4_state_fn
from sgp4.api import Satrec


_SYNTHETIC_NORAD_ID = 99001


def _collapse_synthetic(events: list[ConjunctionEvent]) -> list[ConjunctionEvent]:
    """The injected demo object conjuncts with every craft docked at / near the
    station. Keep only its single closest partner so the alert list is not
    flooded with near-identical synthetic rows."""
    syn = [e for e in events if _SYNTHETIC_NORAD_ID in
           (e.object_a.norad_id, e.object_b.norad_id)]
    if len(syn) <= 1:
        return events
    keep = min(syn, key=lambda e: e.miss_distance_km)
    return [e for e in events if e not in syn] + [keep]


def _sample_evenly(items: list, k: int) -> list:
    if k <= 0 or k >= len(items):
        return list(items)
    idx = np.linspace(0, len(items) - 1, k).round().astype(int)
    return [items[i] for i in dict.fromkeys(idx.tolist())]


class ConjunctionDetector:
    def __init__(
        self,
        tle_source: TLESource,
        filters: list[ConjunctionFilter],
        propagator: SGP4Propagator | None = None,
        *,
        max_objects: int = 400,
        coarse_step_s: float = 60.0,
        refine_threshold_km: float = 25.0,
        report_threshold_km: float = 10.0,
    ):
        self._tle_source = tle_source
        self._filters = list(filters)
        self._propagator = propagator or SGP4Propagator()
        self._max_objects = max_objects
        self._coarse_step_s = coarse_step_s
        self._refine_threshold_km = refine_threshold_km
        self._report_threshold_km = report_threshold_km

    # -- public API ---------------------------------------------------------
    def screen(self, window_hours: float, *, when: datetime | None = None) -> DetectionResult:
        t_start = time.perf_counter()
        when = when or datetime.now(timezone.utc)
        epoch_jd, epoch_fr = run_epoch_jd(when)
        times_s = time_grid_s(window_hours, self._coarse_step_s)

        objects = self._build_objects(times_s, epoch_jd, epoch_fr)
        R = np.stack([o.ephemeris.r_km for o in objects])           # (M, T, 3)

        pairs_before = len(objects) * (len(objects) - 1) // 2
        survivors = self._prefilter_pairs(objects)
        pairs_after = len(survivors)

        events = self._scan_and_refine(objects, R, survivors, times_s, epoch_jd, epoch_fr)
        events = _collapse_synthetic(events)
        events.sort(key=lambda e: e.miss_distance_km)

        return DetectionResult(
            events=events,
            epoch_iso=when.astimezone(timezone.utc).isoformat(),
            window_hours=window_hours,
            object_count=len(objects),
            pairs_before_filter=pairs_before,
            pairs_after_filter=pairs_after,
            screening_latency_s=time.perf_counter() - t_start,
            objects=objects,
            times_s=times_s,
            epoch_jd=epoch_jd,
            epoch_fr=epoch_fr,
        )

    # -- stages -----------------------------------------------------------
    def _build_objects(
        self, times_s: np.ndarray, epoch_jd: float, epoch_fr: float
    ) -> list[ScreeningObject]:
        tles: list[TLE] = _sample_evenly(self._tle_source.fetch(), self._max_objects)
        objects: list[ScreeningObject] = []
        for tle in tles:
            try:
                sat = Satrec.twoline2rv(tle.line1, tle.line2)
                jd = np.full(times_s.shape, epoch_jd)
                fr = epoch_fr + times_s / 86400.0
                err, r, v = sat.sgp4_array(jd, fr)
                if np.any(np.asarray(err) != 0) or not np.all(np.isfinite(r)):
                    continue
                perigee, apogee = apsis_altitudes_km(tle)
                if perigee < -50:                     # decayed / garbage element set
                    continue
                # Store the coarse grid in float32: it only picks the bracket
                # for TCA refinement (which re-propagates in full float64 via
                # Satrec), and halving these arrays roughly halves the peak
                # memory of the pairwise scan below.
                objects.append(
                    ScreeningObject(
                        tle=tle,
                        ephemeris=Ephemeris(
                            times_s,
                            np.asarray(r, dtype=np.float32),
                            np.asarray(v, dtype=np.float32),
                        ),
                        perigee_alt_km=perigee,
                        apogee_alt_km=apogee,
                        satrec=sat,
                    )
                )
            except (ValueError, RuntimeError):
                continue
        return objects

    def _prefilter_pairs(self, objects: list[ScreeningObject]) -> list[tuple[int, int]]:
        survivors: list[tuple[int, int]] = []
        for i in range(len(objects)):
            a = objects[i]
            for j in range(i + 1, len(objects)):
                b = objects[j]
                if all(f.keep_pair(a, b) for f in self._filters):
                    survivors.append((i, j))
        return survivors

    def _scan_and_refine(
        self,
        objects: list[ScreeningObject],
        R: np.ndarray,
        survivors: list[tuple[int, int]],
        times_s: np.ndarray,
        epoch_jd: float,
        epoch_fr: float,
    ) -> list[ConjunctionEvent]:
        if not survivors:
            return []
        I = np.array([p[0] for p in survivors])
        J = np.array([p[1] for p in survivors])

        events: list[ConjunctionEvent] = []
        # Size the pair chunk so the transient ``(chunk, T, 3)`` buffers in the
        # closest-approach scan stay near a fixed budget regardless of the
        # screening window (T grows with window_hours). At float32, ~1e6 => a
        # ~12 MB buffer and a handful of them live at once.
        chunk = min(2000, max(32, 1_000_000 // len(times_s)))
        for s in range(0, len(survivors), chunk):
            sl = slice(s, s + chunk)
            dr = R[I[sl]] - R[J[sl]]                              # (c, T, 3)
            seg_min = segment_closest_approach(dr)                # (c, T-1)
            close_pairs = np.where(seg_min.min(axis=1) < self._refine_threshold_km)[0]
            for local_p in close_pairs:
                p = s + int(local_p)
                i0 = int(np.argmin(seg_min[local_p]))
                a, b = objects[I[p]], objects[J[p]]
                tca_s, miss_km, ra, va, rb, vb = self._refine(
                    a, b, float(times_s[i0]), float(times_s[i0 + 1]),
                    epoch_jd, epoch_fr,
                )
                rel_speed = float(np.linalg.norm(va - vb))
                # Physically attached / co-orbiting (docked craft, deployment
                # pairs): sub-metre separation at near-zero relative speed.
                if miss_km < 0.02 and rel_speed < 0.02:
                    continue
                if miss_km <= self._report_threshold_km:
                    events.append(
                        ConjunctionEvent(
                            object_a=a, object_b=b, tca_s=tca_s,
                            miss_distance_km=miss_km, rel_speed_km_s=rel_speed,
                            r_a_km=ra, v_a_km_s=va, r_b_km=rb, v_b_km_s=vb,
                        )
                    )
        return self._dedupe_keep_closest(events)

    @staticmethod
    def _dedupe_keep_closest(events: list[ConjunctionEvent]) -> list[ConjunctionEvent]:
        best: dict[str, ConjunctionEvent] = {}
        for ev in events:
            cur = best.get(ev.pair_id)
            if cur is None or ev.miss_distance_km < cur.miss_distance_km:
                best[ev.pair_id] = ev
        return list(best.values())

    def _refine(
        self,
        a: ScreeningObject,
        b: ScreeningObject,
        t_lo_s: float,
        t_hi_s: float,
        epoch_jd: float,
        epoch_fr: float,
    ) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        # Pad the bracket slightly so the true minimum is not on a boundary.
        lo = max(0.0, t_lo_s - self._coarse_step_s)
        hi = t_hi_s + self._coarse_step_s
        return refine_tca(
            sgp4_state_fn(a.satrec, epoch_jd, epoch_fr),
            sgp4_state_fn(b.satrec, epoch_jd, epoch_fr),
            lo,
            hi,
        )
