import importlib, inspect, json, os, traceback
from datetime import datetime

os.makedirs("logs", exist_ok=True)
logp = os.path.join("logs","rust_probe.txt")

def log(*a):
    txt = " ".join(str(x) for x in a)
    print(txt)
    with open(logp, "a", encoding="utf-8") as f:
        f.write(txt + "\n")

# fresh log
open(logp, "w", encoding="utf-8").close()

log("=== RUST PROBE START", datetime.utcnow().isoformat(), "UTC ===")

# 1) Importer pyO3-modulen
m = importlib.import_module("cyclegraph_core.cyclegraph_core")
attrs = [a for a in dir(m) if not a.startswith("_")]
log("EXPORTS:", attrs)

# 2) Samle mulige callables
cands = []
for a in attrs:
    try:
        obj = getattr(m, a)
        if callable(obj):
            sig = getattr(obj, "__text_signature__", None) or ""
            doc = (inspect.getdoc(obj) or "")[:200].replace("\\n", " ")
            cands.append((a, sig, doc))
    except Exception:
        pass

log("CANDIDATES:")
for name, sig, doc in cands:
    log(f" - {name} sig={sig} doc={doc}")

# 3) Bygg to payload-varianter
profile_in = {"weight_kg": 90.0, "CdA": 0.32, "Crr": 0.006, "device": "strava"}
est = {"mode": "inline", "version": 1, "force": True}

OBJECT = json.dumps({"estimat": est, "profile": profile_in, "samples": []}, separators=(",", ":"))
TRIPLE = json.dumps([[], profile_in, est], separators=(",", ":"))

def try_call(fn, payload):
    try:
        out = fn(payload)
        return True, out if isinstance(out, str) else str(out)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

# 4) Probe alle callables med OBJECT og TRIPLE
for name, _, _ in cands:
    fn = getattr(m, name)
    if not callable(fn):
        continue
    log(f"\\n== PROBE {name} :: OBJECT ==")
    ok1, res1 = try_call(fn, OBJECT)
    log("ok1=", ok1, "res1_type=", type(res1).__name__)
    log("res1=", (res1[:200] + "...") if isinstance(res1, str) else str(res1)[:200])

    log(f"== PROBE {name} :: TRIPLE ==")
    ok2, res2 = try_call(fn, TRIPLE)
    log("ok2=", ok2, "res2_type=", type(res2).__name__)
    log("res2=", (res2[:200] + "...") if isinstance(res2, str) else str(res2)[:200])

log("=== RUST PROBE END ===")
