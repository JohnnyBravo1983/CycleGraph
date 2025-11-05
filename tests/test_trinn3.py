import json
from cli.rust_bindings import rs_power_json

# --- Last testdata ---
with open("mini_payload.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# --- Kjør Rust-binding ---
s = rs_power_json(data["samples"], data["profile"], data["estimat"])
print("[TEST] Raw output:", s)

# --- Sikre at output er str ---
if not isinstance(s, str):
    print("[TEST] rs_power_json returned dict, dumping to str")
    s = json.dumps(s)

out = json.loads(s)

# --- Kilde (src/source) ---
src = (out.get("source") or out.get("src") or "").lower()
print("[TEST] src =", src)
assert (src.startswith("rust") or src in {"rust_1arg", "rust", "rust_binding"}), f"Invalid src: {src!r}"

# --- Repr kind ---
rk = (out.get("repr_kind")
      or out.get("debug", {}).get("repr_kind")
      or "object")
assert isinstance(rk, str)
assert rk.lower() in {"object", "legacy_tolerant", "triple", "object_v3", "obj"}, f"Invalid repr_kind: {rk!r}"

# --- used_fallback ---
uf = out.get("used_fallback")
if uf is None:
    uf = (out.get("debug") or {}).get("used_fallback")
assert bool((out.get("debug", {}) or {}).get("used_fallback", False)) is False, "Fallback should be False"

print("OK: rust_binding / OBJECT / used_fallback=false ✅")
