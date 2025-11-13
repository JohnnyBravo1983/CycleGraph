# tests/test_trinn15_precision_indicator.py
from server.analysis.calibration15 import compute_estimated_error_and_hint

def test_tr15_estimated_error_and_hint_basic():
    profile = {
        "rider_weight_kg": 83.0,
        "bike_weight_kg": 8.0,
        "tire_width_mm": 28,
        "tire_quality": "performance",
        "bike_type": "road",
        "cda": 0.30,
    }
    weather = {"wind_ms": 2.0, "condition": "clear"}
    rng, hint, completeness = compute_estimated_error_and_hint(profile, weather)
    assert isinstance(rng, list) and len(rng) == 2
    assert 2.0 <= rng[0] <= 20.0 and 2.0 <= rng[1] <= 20.0
    assert hint == "normal"
    assert 0 <= completeness <= 100

def test_tr15_windy_and_wet_hints():
    profile = {}
    w1 = {"wind_ms": 5.0}
    w2 = {"condition": "wet"}
    rng1, hint1, _ = compute_estimated_error_and_hint(profile, w1)
    rng2, hint2, _ = compute_estimated_error_and_hint(profile, w2)
    assert hint1 == "windy"
    assert hint2 == "wet"
    assert 2.0 <= rng1[0] <= rng1[1] <= 20.0
    assert 2.0 <= rng2[0] <= rng2[1] <= 20.0
