"""Central configuration. All tunable thresholds and window sizes live here so no
other module hard-codes them."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENTIDE_", env_file=".env", extra="ignore")

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]

    # --- TLE ingest ---
    # CelesTrak GP groups to screen. Chosen to guarantee an interesting demo:
    # dense constellations + known debris clouds produce frequent close approaches.
    tle_groups: list[str] = [
        "stations",
        "cosmos-2251-debris",
        "iridium-33-debris",
        "cosmos-1408-debris",
        "fengyun-1c-debris",
    ]
    tle_cache_ttl_s: int = 3600
    tle_timeout_s: float = 20.0
    # Cap the screened set so a live /conjunctions call stays interactive and
    # the pairwise scan's peak memory fits a small (512 MB) instance.
    max_objects: int = 250
    # How many distinct screening windows to keep cached at once. Each entry
    # retains a full DetectionResult, so this bounds that retention.
    detection_cache_size: int = 3

    # Inject one guaranteed synthetic high-Pc conjunction so the maneuver
    # rejection demo always has something to act on. Flagged synthetic=true in
    # the API. Set false for a purely real-data run.
    demo_inject_scenario: bool = True
    demo_target_hint: str | None = None       # e.g. "ISS", "STARLINK-1007"

    # --- Propagation / detection ---
    default_window_hours: int = 48
    coarse_step_s: int = 60
    # Pairs whose coarse minimum separation is under this are refined.
    refine_threshold_km: float = 25.0
    # Refined events closer than this are reported as conjunctions.
    report_threshold_km: float = 10.0
    # APSIS filter altitude pad (km) added to each side of the perigee/apogee band.
    apsis_pad_km: float = 15.0

    # --- Risk model (Foster-Estes) ---
    # Default per-object 1-sigma position uncertainty in the RTN frame (metres).
    # km-scale, along-track dominated: representative of propagated TLE error.
    sigma_radial_m: float = 500.0
    sigma_intrack_m: float = 2000.0
    sigma_crosstrack_m: float = 1000.0
    intrack_growth_m_per_hour: float = 120.0
    # Hard-body radius per object (metres); combined HBR is the sum.
    hard_body_radius_m: float = 5.0
    # Risk tier cut points on collision probability. Tightened for a crewed-asset
    # posture: "High" at 1e-5 (many operators escalate crewed conjunctions here),
    # not the 1e-4 used for routine robotic assets.
    pc_high: float = 1e-5
    pc_medium: float = 1e-7

    # --- Maneuver search ---
    maneuver_dv_grid_mps: list[float] = [0.02, 0.05, 0.1, 0.2, 0.5]
    # Lead time before TCA at which the avoidance burn is executed (hours).
    maneuver_lead_hours: float = 12.0
    # A re-screened candidate is rejected if it leaves residual Pc above this,
    # or if it creates any *new* conjunction above this.
    maneuver_pc_reject: float = 1e-6


@lru_cache
def get_settings() -> Settings:
    return Settings()
