# tests/test_publish.py
import pytest
from cyclegraph.strava_publish import publish_precision_watt, HttpResponse, make_publish_hash

class FakeTransport:
    def __init__(self, statuses):
        # statuses: liste av HTTP-statuskoder som skal returneres per kall
        self.statuses = list(statuses)
        self.calls = 0
        self.payloads = []

    def patch_activity(self, activity_id, payload, token):
        self.calls += 1
        self.payloads.append((activity_id, payload, token))
        status = self.statuses.pop(0) if self.statuses else 200
        return HttpResponse(status=status, body={"ok": True})

def no_sleep(_seconds: float) -> None:
    # injiseres for å unngå reell venting i tester
    pass

def test_publish_success_200():
    tr = FakeTransport([200])
    res = publish_precision_watt(
        activity_id=123, precision_watt=253.7, precision_watt_ci=18.2,
        token="t", previous_publish_hash=None, transport=tr, sleep=no_sleep
    )
    assert res.state == "done"
    assert res.hash == make_publish_hash(123, 253.7, 18.2)
    assert res.attempts == 1
    assert tr.calls == 1
    # Beskrivelse skal inneholde tekst for PW
    assert "description" in tr.payloads[0][1]
    assert "Precision Watt" in tr.payloads[0][1]["description"]

def test_publish_retry_then_200_on_429():
    tr = FakeTransport([429, 200])
    res = publish_precision_watt(
        activity_id=1, precision_watt=200.0, precision_watt_ci=None,
        token="t", previous_publish_hash=None, transport=tr, sleep=no_sleep
    )
    assert res.state == "done"
    assert res.attempts == 2
    assert tr.calls == 2

def test_publish_fail_429_after_max_attempts():
    tr = FakeTransport([429, 429, 429])
    res = publish_precision_watt(
        activity_id=1, precision_watt=200.0, precision_watt_ci=None,
        token="t", previous_publish_hash=None, transport=tr, sleep=no_sleep, max_attempts=3
    )
    assert res.state == "failed"
    assert "Rate limited" in (res.message or "")
    assert tr.calls == 3

@pytest.mark.parametrize("code", [401, 403])
def test_publish_fail_auth(code):
    tr = FakeTransport([code])
    res = publish_precision_watt(
        activity_id=1, precision_watt=220.0, precision_watt_ci=10.0,
        token="bad", previous_publish_hash=None, transport=tr, sleep=no_sleep
    )
    assert res.state == "failed"
    assert "error" in (res.message or "").lower()
    assert tr.calls == 1

def test_idempotent_skip_if_same_hash():
    h = make_publish_hash(9, 300.0, None)
    tr = FakeTransport([200])  # skal ikke brukes
    res = publish_precision_watt(
        activity_id=9, precision_watt=300.0, precision_watt_ci=None,
        token="t", previous_publish_hash=h, transport=tr, sleep=no_sleep
    )
    assert res.state == "done"
    assert res.attempts == 0
    assert tr.calls == 0
