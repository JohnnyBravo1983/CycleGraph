import sys
try:
    import cyclegraph_core as cg
    print("[OK] import cyclegraph_core")
    print("dir(cyclegraph_core):", [x for x in dir(cg) if "compute" in x.lower()])
    print("has compute_power_with_wind_json:", hasattr(cg, "compute_power_with_wind_json"))
except Exception as e:
    print("[ERR] import:", e)
    sys.exit(1)