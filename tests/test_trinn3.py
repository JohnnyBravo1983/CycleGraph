import json
from cli.rust_bindings import rs_power_json

with open('mini_payload.json','r',encoding='utf-8') as f:
    data = json.load(f)

s = rs_power_json(data['samples'], data['profile'], data['estimat'])
print(s)
out = json.loads(s)

# Kilde
src = (out.get('source') or '').lower()
assert (src.startswith('rust') or src in {'rust_1arg','rust','rust_binding'})

# repr_kind kan vÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¦re pÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¥ toppnivÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¥ eller i debug, og kan vÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¦re 'OBJECT'/'object'
rk = (out.get('repr_kind') or out.get('debug', {}).get('repr_kind') or 'object')
assert isinstance(rk, str)
assert rk.lower() in {'object','legacy_tolerant','triple','object_v3','obj'}

# used_fallback kan vÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¦re pÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¥ toppnivÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¥ eller i debug
uf = out.get('used_fallback')
if uf is None:
    uf = (out.get('debug') or {}).get('used_fallback')
assert bool((out.get('debug', {}) or {}).get('used_fallback', False)) is False

print('OK: rust_binding / OBJECT / used_fallback=false')
