import pytest
from cli.strava_client import StravaClient

class DummyResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

@pytest.fixture
def dummy_client(monkeypatch):
    client = StravaClient()
    monkeypatch.setattr(client, "resolve_target_activity_id", lambda target=None: "123")
    monkeypatch.setattr("requests.request", lambda *a, **k: DummyResp())
    return client

def test_publish_to_strava_comment_and_description(dummy_client):
    dummy_client.publish_to_strava(
        pieces={"comment": "Hei", "description": "Test"},
        activity_id="latest",
        dry_run=True,
        
    )
