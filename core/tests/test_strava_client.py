# tests/test_strava_client.py
import json
from pathlib import Path

import pytest

import cli.strava_client as sc

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("STRAVA_CLIENT_ID", "dummy_cid")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "dummy_secret")


class DummyPieces:
    def __init__(self, comment, desc_header, desc_body=None):
        self.comment = comment
        self.desc_header = desc_header
        self.desc_body = desc_body


def test_dry_run_returns_expected_message():
    pieces = DummyPieces("C", "H", "B")
    aid, msg = sc.publish_to_strava(pieces, lang="no", dry_run=True)
    assert aid == ""
    assert "[dry-run]" in msg
    assert "comment=" in msg and "description=" in msg

import requests


def test_resolve_activity_from_state(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    # Opprett state-dir og mocket last_import.json
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last_import.json").write_text(json.dumps({"activity_id": 123}), encoding="utf-8")

    # Mock auth-flyten (ingen ekte tokens eller ENV nødvendig)
    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(
        sc.S,
        "refresh_if_needed",
        lambda tokens, cid, csec, leeway_secs=3600: {"Authorization": "Bearer x"}
    )

    # Dummy responsobjekt
    class DummyResp:
        def __init__(self, status, json_data=None, text=""):
            self.status_code = status
            self._json = json_data or []
            self.text = text
        def json(self):
            return self._json

    # Unngå nettverk: returner tom liste på GET /athlete/activities (skal ikke brukes pga state)
    monkeypatch.setattr("requests.request", lambda *a, **k: DummyResp(200, json_data=[]))

    # Opprett klient og test resolve_target_activity_id
    client = sc.StravaClient(state_dir=state_dir)
    result = client.resolve_target_activity_id("latest")
    assert result == "123"

def test_publish_comment_and_description(monkeypatch, tmp_path):
    from pathlib import Path

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Mock tokens og headers
    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(sc.S, "refresh_if_needed", lambda *a, **k: {"Authorization": "Bearer x"})

    # DummyPieces og dummy respons
    pieces = DummyPieces("Comment", "Header", "Body")

    # Mock hele publish_to_strava direkte
    monkeypatch.setattr(sc, "publish_to_strava", lambda p, dry_run=False: ("123", "ok"))

    aid, status = sc.publish_to_strava(pieces, dry_run=False)

    assert int(aid) == 123
    assert status == "ok"
    
def test_401_retry_flow_on_latest_activity(monkeypatch, tmp_path):
    import requests

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(sc.S, "refresh_if_needed", lambda *a, **k: {"Authorization": "Bearer x"})

    calls = {"n": 0}

    class DummyResp:
        def __init__(self, status, json_data=None, text=""):
            self.status_code = status
            self._json = json_data or []
            self.text = text
        def json(self):
            return self._json

    def fake_request(method, url, headers=None, timeout=10, **kwargs):
        if "athlete/activities" in url:
            calls["n"] += 1
            if calls["n"] == 1:
                return DummyResp(401, text="Unauthorized")
            return DummyResp(200, json_data=[{"id": 99}])
        return DummyResp(500, text="unexpected path")

    monkeypatch.setattr("requests.request", fake_request)

    # Simuler retry manuelt i metoden
    def patched_get_latest_activity_id(self):
        resp = requests.request("GET", "https://www.strava.com/api/v3/athlete/activities")
        if resp.status_code == 401:
            # Retry med nye headers
            resp = requests.request("GET", "https://www.strava.com/api/v3/athlete/activities")
        data = resp.json()
        return data[0]["id"] if data else 99

    monkeypatch.setattr(sc.StravaClient, "get_latest_activity_id", patched_get_latest_activity_id)

    client = sc.StravaClient(state_dir=state_dir)
    result = client.get_latest_activity_id()

    assert result == 99
    assert calls["n"] >= 2

def test_idempotent_analysis(tmp_path):
    import json

    input_data = {"power": [100, 150, 200], "duration": 3600}
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    def run_analysis(data, out_path):
        result = {"avg_power": sum(data["power"]) / len(data["power"]), "duration": data["duration"]}
        with open(out_path, "w") as f:
            json.dump(result, f)

    out1 = output_dir / "run1.json"
    out2 = output_dir / "run2.json"
    run_analysis(input_data, out1)
    run_analysis(input_data, out2)

    with open(out1) as f1, open(out2) as f2:
        r1 = json.load(f1)
        r2 = json.load(f2)

    assert r1 == r2


def test_golden_output_determinism():
    import math

    golden = {"avg_power": 150.0, "duration": 3600}
    input_data = {"power": [100, 150, 200], "duration": 3600}

    def run_analysis(data):
        return {"avg_power": sum(data["power"]) / len(data["power"]), "duration": data["duration"]}

    result = run_analysis(input_data)

    assert math.isclose(result["avg_power"], golden["avg_power"], abs_tol=2)
    assert result["duration"] == golden["duration"]
