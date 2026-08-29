"""End-to-end API tests. The container is pointed at the fixture catalog (plus
the injected scenario) so no network call is made."""
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services.tle_fetch import FileTLESource


@pytest.fixture
def client(monkeypatch):
    import app.container as container_mod

    fixture = str(pathlib.Path(__file__).parent / "fixtures" / "sample_tles.txt")
    settings = Settings(max_objects=120, default_window_hours=48,
                        coarse_step_s=60.0, demo_inject_scenario=True)
    c = container_mod.Container(settings=settings)
    # Swap the CelesTrak source for the local fixture, keep scenario injection.
    from app.services.scenario import ScenarioInjectingTLESource

    base = FileTLESource(fixture)
    c.scenario_source = ScenarioInjectingTLESource(
        base, window_hours=48.0, target_name_hint="ISS (ZARYA)"
    )
    c.detector._tle_source = c.scenario_source
    monkeypatch.setattr(container_mod, "_container", c)

    from app.main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_conjunctions_endpoint(client):
    r = client.get("/conjunctions", params={"window_hours": 48})
    assert r.status_code == 200
    body = r.json()
    assert body["object_count"] > 50
    assert body["pairs_before_filter"] > body["pairs_after_filter"]
    assert 0.0 <= body["prefilter_reduction_rate"] <= 1.0
    assert body["conjunctions"], "expected non-empty conjunction list"

    synthetic = [c for c in body["conjunctions"] if c["synthetic"]]
    assert synthetic, "the injected scenario should appear"
    s = synthetic[0]
    assert s["miss_distance_km"] < 2.0
    assert s["pc"] is not None and s["pc"] > 1e-6
    assert s["risk_tier"] in ("Medium", "High")
    assert s["conjunction_id"]


def test_recommend_maneuver_endpoint_shows_rejections(client):
    body = client.get("/conjunctions", params={"window_hours": 48}).json()
    target_conj = next(c for c in body["conjunctions"] if c["synthetic"])
    # Maneuver the real asset, not the synthetic debris.
    obj = target_conj["object_a"] if target_conj["object_a"]["norad_id"] != 99001 \
        else target_conj["object_b"]

    r = client.post("/recommend-maneuver", json={
        "object_id": obj["norad_id"],
        "conjunction_id": target_conj["conjunction_id"],
    })
    assert r.status_code == 200
    m = r.json()
    assert m["candidates_generated"] == 30
    assert m["candidates_rejected"] >= 1, "the demo needs at least one rejected candidate"
    assert m["rejected"], "rejected list must be populated for explainability"
    assert any(c["rejection_reason"] for c in m["rejected"])
    # If anything was recommended it must be genuinely safe.
    for rec in m["recommended"]:
        assert rec["accepted"] is True
        assert rec["residual_pc"] < 1e-6


def test_conjunctions_refresh_recomputes_without_error(client):
    """Recompute drops the TLE cache and forces a fresh screening run."""
    a = client.get("/conjunctions", params={"window_hours": 48})
    b = client.get("/conjunctions", params={"window_hours": 48, "refresh": "true"})
    assert a.status_code == 200 and b.status_code == 200
    assert b.json()["conjunctions"], "refresh must still return a populated list"


def test_separation_series_is_dense_enough_to_reach_the_miss_distance(client):
    """The screening grid is 60 s, but the encounter is a sharp V. The endpoint
    splices a fine grid around TCA so the plotted curve actually reaches the
    refined miss distance instead of bottoming out hundreds of km above it."""
    body = client.get("/conjunctions", params={"window_hours": 48}).json()
    conj = next(c for c in body["conjunctions"] if c["synthetic"])

    r = client.get(f"/conjunctions/{conj['conjunction_id']}/separation")
    assert r.status_code == 200
    s = r.json()
    seps = s["separation_km"]
    times = s["times_hours"]
    assert len(seps) == len(times) > 100

    # The minimum of the returned curve must land essentially on the miss distance.
    assert min(seps) == pytest.approx(s["miss_distance_km"], abs=0.05)

    # There must be sub-second-spaced samples straddling TCA (the spliced grid).
    near = [t for t in times if abs(t - s["tca_hours"]) <= 3.5 / 60.0]
    assert len(near) > 200


def test_geometry_is_windowed_around_tca(client):
    body = client.get("/conjunctions", params={"window_hours": 48}).json()
    conj = next(c for c in body["conjunctions"] if c["synthetic"])

    r = client.get(f"/conjunctions/{conj['conjunction_id']}/geometry", params={"window_min": 60})
    assert r.status_code == 200
    g = r.json()
    ts = g["times_s"]
    assert len(ts) == len(g["object_a"]["path_km"]) == len(g["object_b"]["path_km"]) > 100
    # Every sample within the requested window of TCA.
    assert all(abs(x - g["tca_s"]) <= 60 * 60 + 1 for x in ts)
    # The two paths reach the miss distance at tca_index.
    import numpy as np

    a = np.array(g["object_a"]["path_km"][g["tca_index"]])
    b = np.array(g["object_b"]["path_km"][g["tca_index"]])
    assert np.linalg.norm(a - b) == pytest.approx(g["miss_distance_km"], abs=0.1)


def test_recommend_maneuver_unknown_conjunction_404(client):
    r = client.post("/recommend-maneuver",
                    json={"object_id": 25544, "conjunction_id": "1-2"})
    assert r.status_code == 404


def test_metrics_endpoint_has_real_numbers(client):
    client.get("/conjunctions", params={"window_hours": 48})
    r = client.get("/metrics")
    assert r.status_code == 200
    m = r.json()
    assert m["prefilter_reduction_rate"] is not None
    assert m["pairs_before_filter"] > 0
    assert m["end_to_end_screening_latency_s"] > 0
    assert m["live_catalog_objects"] > 50
