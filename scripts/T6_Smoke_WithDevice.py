import asyncio, types, importlib
m = importlib.import_module("server.routes.sessions")

class R:
    url = types.SimpleNamespace(query="")
    async def json(self):
        return {
            "samples":[
                {"t":0.0,"v_ms":10.0,"device_watts":210},
                {"t":1.0,"v_ms":10.0,"device_watts":215},
                {"t":2.0,"v_ms":10.0,"device_watts":205},
                {"t":3.0,"v_ms":10.0,"device_watts":208}
            ],
            "profile":{"cda":0.3,"crr":0.004,"total_weight":80.0,"crank_eff_pct":95.5},
            "weather":None
        }

async def run():
    r = await m.analyze_session("s2", R(), False, False, 0)
    met = r.get("metrics", {})
    print(met.get("calibrated"), met.get("calibration_status"), met.get("calibration_mae"))

asyncio.run(run())
