# tests/test_analyze_series.py
from fastapi.testclient import TestClient
from app import app  # tilpass hvis din app heter annerledes

client = TestClient(app)
BASE = "/api/sessions"

def post(sid, profile, force=True, no_weather=True):
    return client.post(
        f"{BASE}/{sid}/analyze?force_recompute={str(force).lower()}&no_weather={str(no_weather).lower()}",
        json={"profile": profile}
    )

def test_force_recompute_ignores_persist():
    B = {"CdA": 0.32, "Crr": 0.006, "weight_kg": 90.0, "device": "strava"}
    r = post("rideX", B, force=True, no_weather=True)
    assert r.status_code == 200
    j = r.json()
    assert j["metrics"]["profile_used"] == B
    assert j["debug"]["force_recompute"] is True
    assert j["debug"]["ignored_persist"] is True
    assert j["debug"]["reason"] == "ok"

def test_metrics_vary_with_CdA():
    base = {"Crr": 0.004, "weight_kg": 78.0, "device": "strava"}
    p1 = {"CdA": 0.28, **base}
    p2 = {"CdA": 0.32, **base}
    m1 = post("rideY", p1).json()["metrics"]
    m2 = post("rideY", p2).json()["metrics"]
    assert m2["drag_watt"] > m1["drag_watt"]
    assert (m2["precision_watt"] >= m1["precision_watt"]) or (m2["total_watt"] > m1["total_watt"])

def test_metrics_vary_with_Crr():
    base = {"CdA": 0.30, "weight_kg": 78.0, "device": "strava"}
    p1 = {"Crr": 0.004, **base}
    p2 = {"Crr": 0.006, **base}
    m1 = post("rideZ", p1).json()["metrics"]
    m2 = post("rideZ", p2).json()["metrics"]
    assert m2["rolling_watt"] > m1["rolling_watt"]
    assert m2["total_watt"] >= m1["total_watt"]

def test_metrics_vary_with_weight():
    base = {"CdA": 0.30, "Crr": 0.004, "device": "strava"}
    p1 = {"weight_kg": 78.0, **base}
    p2 = {"weight_kg": 90.0, **base}
    m1 = post("rideW", p1).json()["metrics"]
    m2 = post("rideW", p2).json()["metrics"]
    assert m2["rolling_watt"] > m1["rolling_watt"]
    assert m2["total_watt"] >= m1["total_watt"]

def test_no_weather_in_trinn3():
    p = {"CdA": 0.30, "Crr": 0.005, "weight_kg": 82.0, "device": "zwift"}
    m = post("rideT3", p, force=True, no_weather=True).json()["metrics"]
    assert m["weather_applied"] is False
