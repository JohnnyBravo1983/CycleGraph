import asyncio, types, importlib
m = importlib.import_module("server.routes.sessions")

class R:
    url = types.SimpleNamespace(query="")
    async def json(self):
        return {"samples":[{"t":0.0,"v_ms":10.0}], "profile":{}, "weather":None}

async def run():
    r = await m.analyze_session("s1", R(), False, False, 0)
    met = r.get("metrics", {})
    print(met.get("calibrated"), met.get("calibration_status"), met.get("calibration_mae"))

asyncio.run(run())
