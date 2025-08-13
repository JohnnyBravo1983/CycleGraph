# tests/test_strava_client.py
import json
from pathlib import Path

import pytest
import os
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
    assert aid is None
    assert "[dry-run]" in msg
    assert "comment=" in msg and "description=" in msg


def test_resolve_activity_from_state(tmp_path, monkeypatch):
    # Sørg for at state/last_import.json finnes og peker til 42
    state_dir = Path("state")
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last_import.json").write_text(json.dumps({"activity_id": 42}), encoding="utf-8")

    # Mock auth-flyten (ingen ekte tokens eller ENV nødvendig)
    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(
        sc.S, "refresh_if_needed",
        lambda tokens, cid, csec, leeway_secs=3600: {"Authorization": "Bearer x"}
    )

    # Unngå nettverk: returner tom liste på GET /athlete/activities (skal ikke brukes pga state)
    class DummyResp:
        def __init__(self, status, json_data=None, text=""):
            self.status_code = status
            self._json = json_data or []
            self.text = text
        def json(self):
            return self._json

    monkeypatch.setattr("requests.request", lambda *a, **k: DummyResp(200, json_data=[]))

    client = sc.StravaClient()
    assert client.resolve_target_activity_id() == 42


def test_publish_comment_and_description(monkeypatch, tmp_path):
    # Mock tokens/headers via strava_import
    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(
        sc.S, "refresh_if_needed",
        lambda tokens, cid, csec, leeway_secs=3600: {"Authorization": "Bearer x"}
    )

    # Tving target activity id = 123 (hopper over GET /athlete/activities)
    client = sc.StravaClient()
    monkeypatch.setattr(client, "resolve_target_activity_id", lambda: 123)
    # Injiser vår klient når publish_to_strava lager en StravaClient()
    monkeypatch.setattr(sc, "StravaClient", lambda *a, **k: client)

    # Tell antall POST/PUT-kall
    called = {"post": 0, "put": 0}

    class DummyResp:
        def __init__(self, status, json_data=None, text=""):
            self.status_code = status
            self._json = json_data or []
            self.text = text
        def json(self):
            return self._json

    def fake_request(method, url, headers=None, timeout=10, **kwargs):
        # Svar OK på comment og description
        if method == "POST" and "/comments" in url:
            called["post"] += 1
            return DummyResp(201)
        if method == "PUT" and "/activities/" in url:
            called["put"] += 1
            return DummyResp(200)
        # GET /athlete/activities (ikke brukt her, men safe default)
        return DummyResp(200, json_data=[{"id": 123}])

    monkeypatch.setattr("requests.request", fake_request)

    pieces = DummyPieces("Comment", "Header", "Body")
    aid, status = sc.publish_to_strava(pieces, lang="no", dry_run=False)

    assert aid == 123
    assert status == "published"
    assert called["post"] == 1  # create_comment
    assert called["put"] == 1   # update_description


def test_401_retry_flow_on_latest_activity(monkeypatch):
    """
    Verifiser at klienten prøver en gang til med ferske headers ved 401/403.
    """
    # Mock tokens/headers via strava_import
    monkeypatch.setattr(sc.S, "load_tokens", lambda path: {"access_token": "dummy"})
    monkeypatch.setattr(
        sc.S, "refresh_if_needed",
        lambda tokens, cid, csec, leeway_secs=3600: {"Authorization": "Bearer x"}
    )

    class DummyResp:
        def __init__(self, status, json_data=None, text=""):
            self.status_code = status
            self._json = json_data or []
            self.text = text
        def json(self):
            return self._json

    calls = {"n": 0}

    def fake_request(method, url, headers=None, timeout=10, **kwargs):
        calls["n"] += 1
        # Første forsøk gir 401, andre forsøk OK med id
        if "athlete/activities" in url and calls["n"] == 1:
            return DummyResp(401, text="Unauthorized")
        if "athlete/activities" in url and calls["n"] == 2:
            return DummyResp(200, json_data=[{"id": 99}])
        return DummyResp(500, text="unexpected path")

    monkeypatch.setattr("requests.request", fake_request)

    client = sc.StravaClient()
    assert client.get_latest_activity_id() == 99
    assert calls["n"] == 2
