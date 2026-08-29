"""Maneuver generation, re-screening and recommendation (Phase 3 - the core
differentiator).

- :class:`ManeuverGenerator` produces a Delta-v grid (radial / along-track /
  cross-track x a few magnitudes).
- :class:`ManeuverPlanner.re_screen` re-propagates a candidate's post-burn arc
  and re-runs conjunction detection + Pc scoring against the catalog.
- :meth:`ManeuverPlanner.recommend` rejects unsafe candidates and ranks the
  survivors by residual risk -> Delta-v cost -> timing margin.
"""
from __future__ import annotations

import time

import numpy as np

from app.domain import ConjunctionEvent, ManeuverCandidate, ScreeningObject
from app.interfaces.risk_model import RiskModel
from app.services.propagate import TwoBodyPropagator
from app.services.tca import (
    object_state_fn,
    object_states,
    refine_tca,
    segment_closest_approach,
)

_RTN_DIRS: list[tuple[str, tuple[float, float, float]]] = [
    ("+radial", (1, 0, 0)), ("-radial", (-1, 0, 0)),
    ("+along-track", (0, 1, 0)), ("-along-track", (0, -1, 0)),
    ("+cross-track", (0, 0, 1)), ("-cross-track", (0, 0, -1)),
]


def _rtn_basis(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    r_hat = r / np.linalg.norm(r)
    n_hat = np.cross(r, v)
    n_hat = n_hat / np.linalg.norm(n_hat)
    t_hat = np.cross(n_hat, r_hat)
    return np.column_stack([r_hat, t_hat, n_hat])       # RTN -> inertial


class ManeuverGenerator:
    def __init__(self, dv_grid_mps: list[float], lead_hours: float = 12.0):
        self._dv_grid = list(dv_grid_mps)
        self._lead_hours = lead_hours

    def generate(self, event: ConjunctionEvent) -> list[ManeuverCandidate]:
        burn_t = max(0.0, event.tca_s - self._lead_hours * 3600.0)
        out: list[ManeuverCandidate] = []
        for _, direction in _RTN_DIRS:
            d = np.array(direction, dtype=float)
            for mag in self._dv_grid:
                dv = tuple((d * mag).tolist())
                out.append(
                    ManeuverCandidate(
                        dv_rtn_mps=dv,
                        dv_magnitude_mps=float(mag),
                        burn_time_s=burn_t,
                    )
                )
        return out


class ManeuverPlanner:
    def __init__(
        self,
        risk_model: RiskModel,
        *,
        pc_reject: float = 1e-5,
        report_threshold_km: float = 10.0,
        refine_threshold_km: float = 25.0,
        coarse_step_s: float = 60.0,
    ):
        self._model = risk_model
        self._pc_reject = pc_reject
        self._report_km = report_threshold_km
        self._refine_km = refine_threshold_km
        self._step_s = coarse_step_s
        self._twobody = TwoBodyPropagator()

    # -- post-burn trajectory -----------------------------------------
    def post_burn_state_fn(self, target, candidate, epoch_jd, epoch_fr):
        """Return ``(r0_km, v0_km_s, v0_post_km_s, state_fn)`` for the maneuvered
        object (pre-burn state, post-burn velocity, and the trajectory callable).

        ``state_fn`` uses a *differential* model: the object's SGP4 trajectory
        plus the two-body difference between the burned and un-burned arcs from
        the burn state. The bulk of the two-body modelling error cancels in the
        difference, so a zero Delta-v reproduces the SGP4 baseline exactly and a
        real burn is tracked accurately over the screening window.
        """
        base_fn = object_state_fn(target, epoch_jd, epoch_fr)
        r0, v0 = base_fn(candidate.burn_time_s)
        rot = _rtn_basis(r0, v0)                           # RTN -> inertial
        v0_new = v0 + rot @ (np.array(candidate.dv_rtn_mps) / 1000.0)
        t0 = candidate.burn_time_s

        def state_fn(t: float) -> tuple[np.ndarray, np.ndarray]:
            rb, vb = base_fn(t)
            if t <= t0:
                return rb, vb
            burned = self._twobody.propagate_state(r0, v0_new, t0, np.array([t]))
            unburned = self._twobody.propagate_state(r0, v0, t0, np.array([t]))
            dr = burned.r_km[0] - unburned.r_km[0]
            dv = burned.v_km_s[0] - unburned.v_km_s[0]
            return rb + dr, vb + dv

        return r0, v0, v0_new, state_fn

    # -- re-screening ---------------------------------------------------
    def re_screen(
        self,
        target: ScreeningObject,
        secondary: ScreeningObject,
        candidate: ManeuverCandidate,
        catalog: list[ScreeningObject],
        times_s: np.ndarray,
        epoch_jd: float,
        epoch_fr: float,
        *,
        baseline_pc: float,
    ) -> ManeuverCandidate:
        """Populate ``candidate`` with post-burn residual Pc and any new
        conjunctions it creates, then set accepted / rejection_reason."""
        arc_mask = times_s >= candidate.burn_time_s
        arc_times = times_s[arc_mask]
        if arc_times.size < 3:
            candidate.accepted = False
            candidate.rejection_reason = "burn time too close to end of window"
            candidate.timing_margin_hours = round(candidate.burn_time_s / 3600.0, 2)
            return candidate

        # Post-burn trajectory of the maneuvered object: SGP4 baseline plus the
        # two-body burned-minus-unburned difference (see post_burn_state_fn).
        r0, v0, v0_new, target_state = self.post_burn_state_fn(
            target, candidate, epoch_jd, epoch_fr
        )
        base_r, _ = object_states(target, arc_times, epoch_jd, epoch_fr)
        burned = self._twobody.propagate_state(r0, v0_new, candidate.burn_time_s, arc_times)
        unburned = self._twobody.propagate_state(r0, v0, candidate.burn_time_s, arc_times)
        R_target = base_r + (burned.r_km - unburned.r_km)  # (Ta, 3)

        # 3. residual Pc against the original secondary.
        residual_pc = self._pair_pc(
            target, secondary, target_state, times_s, arc_mask, R_target,
            epoch_jd, epoch_fr,
        )
        candidate.residual_pc = residual_pc

        # 4. scan every other catalog object for a *new* conjunction - one that
        #    did not exist on the un-maneuvered trajectory.
        new_hits: list[dict] = []
        base_r_full, _ = object_states(target, times_s, epoch_jd, epoch_fr)
        for other in catalog:
            if other.norad_id in (target.norad_id, secondary.norad_id):
                continue
            # Skip objects that were already close pre-burn (co-orbiting
            # neighbours, docked craft, pre-existing conjunctions): a maneuver
            # cannot be blamed for a conjunction that was there anyway.
            base_gap = np.linalg.norm(base_r_full - other.ephemeris.r_km, axis=1).min()
            if base_gap < self._refine_km:
                continue
            R_other = other.ephemeris.r_km[arc_mask]
            seg_min = segment_closest_approach(R_target - R_other)
            if seg_min.min() >= self._refine_km:
                continue
            i0 = int(np.argmin(seg_min))
            tca, miss, ra, va, rb, vb = refine_tca(
                target_state,
                object_state_fn(other, epoch_jd, epoch_fr),
                max(candidate.burn_time_s, float(arc_times[i0]) - self._step_s),
                float(arc_times[i0 + 1]) + self._step_s,
            )
            if miss > self._report_km:
                continue
            ev = ConjunctionEvent(
                object_a=target, object_b=other, tca_s=tca, miss_distance_km=miss,
                rel_speed_km_s=float(np.linalg.norm(va - vb)),
                r_a_km=ra, v_a_km_s=va, r_b_km=rb, v_b_km_s=vb,
            )
            pc = self._model.collision_probability(ev)
            if pc >= self._pc_reject:
                new_hits.append(
                    {
                        "object_id": other.norad_id,
                        "object_name": other.name,
                        "tca_hours": round(tca / 3600.0, 3),
                        "miss_distance_km": round(miss, 4),
                        "pc": pc,
                    }
                )
        candidate.new_conjunctions = new_hits

        # 5. verdict.
        candidate.timing_margin_hours = round(candidate.burn_time_s / 3600.0, 2)
        if residual_pc >= self._pc_reject:
            candidate.accepted = False
            candidate.rejection_reason = (
                f"residual Pc {residual_pc:.2e} still above reject threshold "
                f"{self._pc_reject:.0e} (baseline was {baseline_pc:.2e})"
            )
        elif new_hits:
            worst = max(new_hits, key=lambda h: h["pc"])
            candidate.accepted = False
            candidate.rejection_reason = (
                f"creates a new conjunction with {worst['object_name']} "
                f"(NORAD {worst['object_id']}): miss {worst['miss_distance_km']} km, "
                f"Pc {worst['pc']:.2e}"
            )
        else:
            candidate.accepted = True
            candidate.rejection_reason = None
        return candidate

    def _pair_pc(
        self, target, secondary, target_state, times_s, arc_mask, R_target,
        epoch_jd, epoch_fr,
    ) -> float:
        R_sec = secondary.ephemeris.r_km[arc_mask]
        arc_times = times_s[arc_mask]
        seg_min = segment_closest_approach(R_target - R_sec)
        if seg_min.min() >= self._refine_km:
            return 0.0
        i0 = int(np.argmin(seg_min))
        tca, miss, ra, va, rb, vb = refine_tca(
            target_state,
            object_state_fn(secondary, epoch_jd, epoch_fr),
            max(float(arc_times[0]), float(arc_times[i0]) - self._step_s),
            float(arc_times[i0 + 1]) + self._step_s,
        )
        if miss > self._report_km:
            return 0.0
        ev = ConjunctionEvent(
            object_a=target, object_b=secondary, tca_s=tca, miss_distance_km=miss,
            rel_speed_km_s=float(np.linalg.norm(va - vb)),
            r_a_km=ra, v_a_km_s=va, r_b_km=rb, v_b_km_s=vb,
        )
        return self._model.collision_probability(ev)

    # -- recommendation ----------------------------------------------------
    def recommend(
        self,
        target: ScreeningObject,
        secondary: ScreeningObject,
        candidates: list[ManeuverCandidate],
        catalog: list[ScreeningObject],
        times_s: np.ndarray,
        epoch_jd: float,
        epoch_fr: float,
        *,
        baseline_pc: float,
    ) -> tuple[list[ManeuverCandidate], dict]:
        t0 = time.perf_counter()
        screened = [
            self.re_screen(
                target, secondary, c, catalog, times_s, epoch_jd, epoch_fr,
                baseline_pc=baseline_pc,
            )
            for c in candidates
        ]
        elapsed = time.perf_counter() - t0
        accepted = [c for c in screened if c.accepted]
        accepted.sort(
            key=lambda c: (
                c.residual_pc if c.residual_pc is not None else 1.0,
                c.dv_magnitude_mps,
                -(c.timing_margin_hours or 0.0),
            )
        )
        stats = {
            "candidates_generated": len(screened),
            "candidates_rejected": len(screened) - len(accepted),
            "rejection_rate": (len(screened) - len(accepted)) / len(screened)
            if screened
            else None,
            "total_rescreen_s": elapsed,
            "rescreen_s_per_candidate": elapsed / len(screened) if screened else None,
        }
        return accepted, stats
