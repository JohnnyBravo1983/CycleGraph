import json
from cyclegraph_core import compute_power_with_wind_json

samples = [
    {"t":0,"v_ms":8.0,"altitude_m":50.0,"heading_deg":0.0,"moving":True,"latitude":59.0,"longitude":10.0},
    {"t":1,"v_ms":9.0,"altitude_m":50.2,"heading_deg":0.0,"moving":True,"latitude":59.0001,"longitude":10.0},
    {"t":2,"v_ms":9.5,"altitude_m":50.4,"heading_deg":0.0,"moving":True,"latitude":59.0002,"longitude":10.0},
]
profile = {"total_weight":78.0,"bike_type":"road","crr":0.005,"cda":0.30,"calibrated":False,"calibration_mae":None,"estimat":True}
weather = {"wind_ms":2.0,"wind_dir_deg":180.0,"air_temp_c":15.0,"air_pressure_hpa":1013.0}

s = compute_power_with_wind_json(json.dumps(samples), json.dumps(profile), json.dumps(weather))
obj = json.loads(s)
print("keys:", obj.keys())
print("len watts:", len(obj.get("watts", [])))
print("head watts:", obj.get("watts", [])[:3])
print("len wind_rel:", len(obj.get("wind_rel", [])))
print("head wind_rel:", obj.get("wind_rel", [])[:3])
print("len v_rel:", len(obj.get("v_rel", [])))
print("head v_rel:", obj.get("v_rel", [])[:3])