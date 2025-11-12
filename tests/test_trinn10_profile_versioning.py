from fastapi.testclient import TestClient
import os, json
from app import app  # rot/app.py

client = TestClient(app)

def _reset_files():
    for p in ["data/profile.json", "logs/profile/profile_versions.jsonl"]:
        try: os.remove(p)
        except FileNotFoundError: pass

def test_get_put_profile_and_audit():
    _reset_files()
    r = client.get("/api/profile/get")
    assert r.status_code == 200
    b = r.json()
    assert "profile" in b and "profile_version" in b and "version_hash" in b and "version_at" in b
    assert isinstance(b["version_hash"], str) and len(b["version_hash"]) == 8
    assert b["profile_version"].startswith("v1-")

    new_prof = {
        "rider_weight_kg": 83.0,
        "bike_type": "road",
        "bike_weight_kg": 8.0,
        "tire_width_mm": 28,
        "tire_quality": "performance",
        "device": "strava",
        "crank_efficiency": 91.0  # ignored
    }
    r2 = client.put("/api/profile/save", json=new_prof)
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["profile_version"].startswith("v1-")
    assert len(b2["version_hash"]) == 8

    audit = os.path.join("logs","profile","profile_versions.jsonl")
    assert os.path.exists(audit)
    with open(audit, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert last["profile_version"] == b2["profile_version"]
    assert last["version_hash"] == b2["version_hash"]

def test_analyze_injects_profile_version_e2e():
    # Kjør E2E mot API-et (ingen intern import/mocking)
    payload = {"samples": [], "profile": {
        "rider_weight_kg": 83.0, "bike_type": "road", "bike_weight_kg": 8.0,
        "tire_width_mm": 28, "tire_quality": "performance", "device": "strava"
    }}
    r = client.post("/api/sessions/x/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()

    # Toppnivå key
    assert "profile_version" in body, body

    # Toppnivå profile_used
    assert "profile_used" in body and isinstance(body["profile_used"], dict)
    assert body["profile_used"].get("profile_version") == body["profile_version"]

    # metrics.profile_used speiling
    m = body.get("metrics") or {}
    mu = m.get("profile_used") or {}
    assert isinstance(mu, dict)
    assert mu.get("profile_version") == body["profile_version"]
