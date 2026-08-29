"""Collision-probability models (strategy implementations)."""
from __future__ import annotations

import numpy as np

from app.domain import ConjunctionEvent
from app.interfaces.risk_model import RiskModel


def _rtn_basis(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Columns [R_hat, T_hat, N_hat] rotating an RTN vector into the inertial
    frame the state is expressed in (TEME here)."""
    r_hat = r / np.linalg.norm(r)
    n_hat = np.cross(r, v)
    n_hat = n_hat / np.linalg.norm(n_hat)
    t_hat = np.cross(n_hat, r_hat)
    return np.column_stack([r_hat, t_hat, n_hat])


class FosterEstesModel(RiskModel):
    """Foster-Estes 2-D collision probability (NASA JSC, 1992).

    The relative position and the combined position covariance at TCA are
    projected onto the conjunction plane (perpendicular to the relative velocity)
    and the 2-D Gaussian is integrated over a circle of radius equal to the
    combined hard-body radius.
    """

    def __init__(
        self,
        sigma_rtn_m: tuple[float, float, float] = (500.0, 2000.0, 1000.0),
        hard_body_radius_m: float = 5.0,
        intrack_growth_m_per_hour: float = 120.0,
        n_radial: int = 60,
        n_theta: int = 120,
    ):
        # TLE-derived state uncertainty is km-scale, dominated by the along-track
        # component, which grows roughly linearly with propagation time. These
        # are deliberately conservative (large) so the model does not understate
        # risk - the high-recall requirement in the spec.
        self._sigma_rtn_km = np.array(sigma_rtn_m) / 1000.0
        self._intrack_growth_km_per_hour = intrack_growth_m_per_hour / 1000.0
        # Combined HBR = sum of two identical spheres.
        self._hbr_km = 2.0 * hard_body_radius_m / 1000.0
        self._n_radial = n_radial
        self._n_theta = n_theta

    @property
    def name(self) -> str:
        return "foster-estes-2d"

    def _covariance_km2(self, event: ConjunctionEvent) -> np.ndarray:
        tca_hours = max(0.0, event.tca_s / 3600.0)
        sigma = self._sigma_rtn_km.copy()
        sigma[1] += self._intrack_growth_km_per_hour * tca_hours
        var = sigma**2
        cov = np.zeros((3, 3))
        for r, v in ((event.r_a_km, event.v_a_km_s), (event.r_b_km, event.v_b_km_s)):
            rot = _rtn_basis(np.asarray(r), np.asarray(v))
            cov += rot @ np.diag(var) @ rot.T
        return cov

    def collision_probability(self, event: ConjunctionEvent) -> float:
        dr = np.asarray(event.r_b_km) - np.asarray(event.r_a_km)
        dv = np.asarray(event.v_b_km_s) - np.asarray(event.v_a_km_s)
        dv_n = np.linalg.norm(dv)
        if dv_n < 1e-9:
            return 0.0

        # Conjunction-plane basis: perpendicular to relative velocity.
        w = dv / dv_n
        eta = np.cross(dr, w)
        if np.linalg.norm(eta) < 1e-12:
            eta = np.cross(w, np.array([1.0, 0.0, 0.0]))
            if np.linalg.norm(eta) < 1e-12:
                eta = np.cross(w, np.array([0.0, 1.0, 0.0]))
        eta = eta / np.linalg.norm(eta)
        xi = np.cross(eta, w)
        M = np.vstack([xi, eta])                       # (2, 3)

        cov2 = M @ self._covariance_km2(event) @ M.T   # (2, 2)
        miss2 = M @ dr                                 # (2,)

        # Diagonalise the 2-D covariance; integrate in its eigenframe.
        evals, evecs = np.linalg.eigh(cov2)
        evals = np.clip(evals, 1e-12, None)
        sx, sy = np.sqrt(evals)
        mx, my = evecs.T @ miss2

        rs = np.linspace(0.0, self._hbr_km, self._n_radial)
        ths = np.linspace(0.0, 2.0 * np.pi, self._n_theta, endpoint=False)
        rr, tt = np.meshgrid(rs, ths, indexing="ij")
        x = rr * np.cos(tt) - mx
        y = rr * np.sin(tt) - my
        integrand = np.exp(-0.5 * ((x / sx) ** 2 + (y / sy) ** 2)) * rr
        dr_step = rs[1] - rs[0] if self._n_radial > 1 else self._hbr_km
        dth = ths[1] - ths[0] if self._n_theta > 1 else 2.0 * np.pi
        pc = integrand.sum() * dr_step * dth / (2.0 * np.pi * sx * sy)
        return float(np.clip(pc, 0.0, 1.0))
