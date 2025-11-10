import json
from cli.rust_bindings import rs_power_json

def run_case(wdir_from_deg, wind_ms):
    samples = [{"t": float(i), "v_ms": 10.0, "altitude_m": 0.0, "heading_deg": 0.0, "moving": True} for i in range(120)]
    profile = {"cda": 0.30, "crr": 0.004, "weight_kg": 90.0, "calibrated": False}
    third   = {"air_temp_c": 8.0, "air_pressure_hpa": 1005.0, "dir_is_from": True,
               "wind_ms": wind_ms, "wind_dir_deg": wdir_from_deg, "debug": 1}
    out = json.loads(rs_power_json(samples, profile, third))
    m = out.get("metrics", {})
    return float(m.get("precision_watt", 0.0)), float(m.get("drag_watt", 0.0))

def test_headwind_vs_calm_vs_tailwind_precision():
    p_head, _ = run_case(0.0,   2.4)   # motvind (fra nord)
    p_calm, _ = run_case(0.0,   0.0)   # stille
    p_tail, _ = run_case(180.0, 2.4)   # medvind (fra sør)
    assert p_head > p_calm > p_tail

def test_headwind_vs_calm_vs_tailwind_drag():
    _, d_head = run_case(0.0,   2.4)
    _, d_calm = run_case(0.0,   0.0)
    _, d_tail = run_case(180.0, 2.4)
    # Dette er forventet fysikk: drag skal øke i motvind og minke i medvind
    assert d_head > d_calm > d_tail
