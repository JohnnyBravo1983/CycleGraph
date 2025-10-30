import json
import cyclegraph_core.cyclegraph_core as cg

def call(x, tag):
    try:
        out = cg.compute_power_with_wind_json(json.dumps(x))
        print(f"OK {tag}: {out[:160]} ...")
    except Exception as e:
        print(f"ERR {tag}:", repr(e))

S = [{"t": 0.0, "v_ms": 6.0, "altitude_m": 0.0}]
P = {"CdA": 0.28, "Crr": 0.004, "weightKg": 78, "device": "strava"}
E = {"mode": "inline", "version": 1, "force": False}

# Basiscases (uten calibrated først)
call({"samples": S, "profile": P, "estimat": E}, "OBJECT uten calibrated")
call([S, P, E], "TRIPLE uten calibrated")

# Med calibrated eksplisitt
P2 = dict(P)
P2["calibrated"] = False
call({"samples": S, "profile": P2, "estimat": E}, "OBJECT med calibrated")
call([S, P2, E], "TRIPLE med calibrated")

# Tomme / manglende samples — skal parses uten å knekke
call({"samples": [], "profile": P2, "estimat": E}, "OBJECT samples tom liste")
call({"profile": P2, "estimat": E}, "OBJECT samples mangler helt")
