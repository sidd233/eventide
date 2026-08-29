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
