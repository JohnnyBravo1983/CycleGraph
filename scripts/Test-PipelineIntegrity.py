# -------------------------------------------------------------
# Test-PipelineIntegrity.py
# Full integritetssjekk for CycleGraph-pipelinen (Python <-> Rust)
# -------------------------------------------------------------
import os, json, math, sys
import numpy as np
import pandas as pd

# -------------------------------------------------------------
# 1) Importer rust-bindings
# -------------------------------------------------------------
sys.path.insert(0, os.getcwd())

def ok(cond, msg):
    if cond:
        print(f"[OK]   {msg}")
    else:
        print(f"[WARN] {msg}")

print("=== PIPELINE INTEGRITY TEST START ===")

try:
    import cli.rust_bindings as rb
    from cli.rust_bindings import rs_power_json
    print("[OK]   Import av rust_bindings: SUKSESS")
except Exception as e:
    print(f"[FAIL] Kunne ikke importere rust_bindings: {e}")
    sys.exit(1)

# -------------------------------------------------------------
# 2) Dummydata (kan byttes ut med ekte session-data)
# -------------------------------------------------------------
samples = [
    {"t": 0.0, "v_ms": 0.0, "lat_deg": 59.0, "lon_deg": 10.0, "heading_deg": 0.0, "altitude_m": 10.0},
    {"t": 1.0, "v_ms": 5.0, "lat_deg": 59.0001, "lon_deg": 10.0001, "heading_deg": 5.0, "altitude_m": 10.5},
    {"t": 2.0, "v_ms": 6.0, "lat_deg": 59.0002, "lon_deg": 10.0002, "heading_deg": 10.0, "altitude_m": 11.0},
]

profile = {
    "cda": 0.30, "crr": 0.004, "total_weight": 80.0,
    "bike_type": None, "calibrated": False, "estimat": False
}

weather = {
    "wind_ms": 2.0, "wind_dir_deg": 30.0,
    "air_temp_c": 15.0, "air_pressure_hpa": 1013.25
}

# -------------------------------------------------------------
# 3) Inputsanity
# -------------------------------------------------------------
df = pd.DataFrame(samples)

print("\n-- INPUT VALIDATION --")
ok(df["t"].is_monotonic_increasing, "Tid er monotont økende")
ok(df["v_ms"].between(0, 25).all(), "Fart (v_ms) innenfor realistisk område 0–25 m/s")
ok(df["heading_deg"].between(0, 360).all(), "Heading innenfor 0–360 grader")
ok(df["lat_deg"].notna().all() and df["lon_deg"].notna().all(), "Lat/lon uten NaN")
ok(isinstance(weather["wind_dir_deg"], (int, float)), "Vindretning numerisk")
ok(isinstance(weather["wind_ms"], (int, float)), "Vindhastighet numerisk")

# -------------------------------------------------------------
# 4) JSON roundtrip
# -------------------------------------------------------------
print("\n-- JSON ROUNDTRIP --")
try:
    j = json.dumps({"samples": samples, "profile": profile, "weather": weather})
    j2 = json.loads(j)
    ok("samples" in j2 and "weather" in j2, "JSON-roundtrip ok med korrekte nøkler")
except Exception as e:
    print("[FAIL] JSON roundtrip:", e)

# -------------------------------------------------------------
# 5) Rust-kall og outputvalidering
# -------------------------------------------------------------
print("\n-- RUST OUTPUT VALIDATION --")
try:
    out_json = rs_power_json(samples, profile, weather)
    result = json.loads(out_json)

    ok(isinstance(result, dict), "Rust-return verdi er JSON-objekt")
    ok("v_ms" in result, "Output har v_ms")
    ok("total_watt" in result, "Output har total_watt")

    # Sjekk lengde hvis v_ms er liste
    if isinstance(result["v_ms"], list):
        ok(len(result["v_ms"]) == len(samples), "Output-lengde matcher input")
    else:
        print("[WARN] v_ms er ikke en liste – uvanlig struktur")

    # Håndter float eller liste for total_watt
    tw = result["total_watt"]
    if isinstance(tw, list):
        ok(not any(math.isnan(x) for x in tw), "Ingen NaN i total_watt (liste)")
    elif isinstance(tw, (int, float)):
        ok(not math.isnan(tw), "Ingen NaN i total_watt (float)")
    else:
        print(f"[WARN] Uventet type for total_watt: {type(tw)}")

except Exception as e:
    print(f"[FAIL] Rust-kall feilet: {e}")
    result = None

# -------------------------------------------------------------
# 6) Enhets- og fortegnkontroll
# -------------------------------------------------------------
print("\n-- UNIT / SIGN CHECK --")
if result:
    # Bare kolonner med listeverdier tas med i DataFrame
    list_cols = {k: v for k, v in result.items() if isinstance(v, list)}
    scalar_cols = {k: v for k, v in result.items() if not isinstance(v, list)}

    if list_cols:
        df_r = pd.DataFrame(list_cols)
        print(f"[INFO] Konstruert DataFrame med {len(df_r.columns)} kolonner og {len(df_r)} rader.")
        if "gravity_watt" in df_r and "grade" in df_r:
            sign_err = ((df_r["gravity_watt"] > 0) & (df_r["grade"] < 0)).any()
            ok(not sign_err, "Fortegn på gravity_watt følger stigning")
        else:
            print("[WARN] gravity_watt eller grade ikke funnet i resultatet")
    else:
        print("[WARN] Ingen listefelter i resultatet – hopper over DataFrame-sjekk")

    # Vis scalars for inspeksjon
    if scalar_cols:
        print("[INFO] Skalare verdier i output:")
        for k, v in scalar_cols.items():
            print(f"       {k}: {v} ({type(v).__name__})")

# -------------------------------------------------------------
# 7) Schema snapshot
# -------------------------------------------------------------
if result:
    print("\n-- SCHEMA SNAPSHOT --")
    for k, v in result.items():
        tname = type(v).__name__
        shape = f"len={len(v)}" if isinstance(v, (list, tuple)) else "scalar"
        print(f"  {k:<18} | {tname:<10} | {shape}")

# -------------------------------------------------------------
# 8) Oppsummering
# -------------------------------------------------------------
print("\n=== PIPELINE INTEGRITY TEST FERDIG ===")
print(f"Samples: {len(samples)}, Keys i output: {list(result.keys()) if result else 'Ingen'}")
