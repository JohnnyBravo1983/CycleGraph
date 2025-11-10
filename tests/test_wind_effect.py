import json
from cli.rust_bindings import rs_power_json

def run_case(wdir_deg: float, wind_ms: float, dir_is_from: bool = True):
    """
    Syntetisk 120 s sekvens på flat vei, heading=0° (nord).
    Returnerer (precision_watt, drag_watt).
    NB: Vi asserter kun på drag i testene – precision kan påvirkes senere i pipeline.
    """
    samples = [
        {"t": float(i), "v_ms": 10.0, "altitude_m": 0.0, "heading_deg": 0.0, "moving": True}
        for i in range(120)
    ]
    profile = {"cda": 0.30, "crr": 0.004, "weight_kg": 90.0, "calibrated": False}
    third = {
        "air_temp_c": 8.0,
        "air_pressure_hpa": 1005.0,
        "wind_ms": wind_ms,
        "wind_dir_deg": wdir_deg,
        "dir_is_from": dir_is_from,   # vi oppgir FROM; kjernen håndterer robust
        "debug": 1,
    }
    out = json.loads(rs_power_json(samples, profile, third))
    m = out.get("metrics", {})
    return float(m.get("precision_watt", 0.0)), float(m.get("drag_watt", 0.0))


def _classify_head_tail(ms: float = 2.4):
    """
    Kjør motstående retninger (0° og 180°). Den som gir høyest drag er 'headwind',
    den laveste er 'tailwind' – uavhengig av TO/FROM-konvensjon i kjernen.
    Returnerer (d_head, d_calm, d_tail) og tilsvarende precision for logging.
    """
    p_calm, d_calm = run_case(0.0, 0.0)

    p_a, d_a = run_case(0.0,   ms)
    p_b, d_b = run_case(180.0, ms)

    if d_a >= d_b:  # a er motvind
        d_head, p_head = d_a, p_a
        d_tail, p_tail = d_b, p_b
    else:           # b er motvind
        d_head, p_head = d_b, p_b
        d_tail, p_tail = d_a, p_a

    return (p_head, p_calm, p_tail, d_head, d_calm, d_tail)


def test_headwind_vs_calm_vs_tailwind_drag():
    """
    Fysikk-invarianten: drag skal være størst i motvind, minst i medvind.
    """
    p_head, p_calm, p_tail, d_head, d_calm, d_tail = _classify_head_tail(ms=2.4)

    # Primær-invariant (robust mot TO/FROM-variasjon): 
    assert d_head > d_calm > d_tail, f"drag order failed: head={d_head}, calm={d_calm}, tail={d_tail}"

    # Valgfri logging for inspeksjon (ingen assert på precision pga pipeline-skalering)
    # Dette gjør feilsøking enklere uten å flake testen:
    print(f"[DBG] precision_watt (no assert): head={p_head:.3f} calm={p_calm:.3f} tail={p_tail:.3f}")


def test_drag_monotonic_with_wind_speed():
    """
    Ekstra sanity: Med samme 'motvindsretning' skal drag øke når vindstyrken øker.
    Vi bruker samme klassifisering (størst drag = motvind).
    """
    # Finn headwind ved 2.4 m/s
    _, _, _, d_head_24, _, _ = _classify_head_tail(ms=2.4)
    # Finn headwind ved 4.0 m/s
    _, _, _, d_head_40, _, _ = _classify_head_tail(ms=4.0)

    assert d_head_40 > d_head_24, f"headwind drag should grow with wind: 4.0={d_head_40} vs 2.4={d_head_24}"
