import json, cyclegraph_core as cg
print("cyclegraph_core version:", getattr(cg, "__version__", "n/a"))

obj = {
  "estimat": {"mode":"inline","version":1,"force":False},
  "profile": {"CdA":0.28,"Crr":0.004,"weightKg":78.0},
  "samples": [{"t":0,"v_ms":6.0}]
}
tri = [
  [{"t":0,"v_ms":6.0}],
  {"CdA":0.28,"Crr":0.004,"weightKg":78.0},
  {"mode":"inline","version":1,"force":False}
]

def try_call(label, payload):
    try:
        s = json.dumps(payload)
        r = cg.compute_power_with_wind_json(s)
        print(label, "OK:", (r[:160] if isinstance(r,str) else str(r)) )
    except Exception as e:
        print(label, "ERR:", repr(e))

try_call("OBJECT(estimat)", obj)
obj2 = dict(obj); obj2["estimate"] = obj2["estimat"]; del obj2["estimat"]
try_call("OBJECT(estimate)", obj2)
try_call("TRIPLE", tri)
