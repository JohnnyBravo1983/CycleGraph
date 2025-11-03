import json
from cli.rust_bindings import rs_power_json

with open('mini_payload.json','r',encoding='utf-8') as f:
    data = json.load(f)

s = rs_power_json(data['samples'], data['profile'], data['estimat'])
print(s)
out = json.loads(s)

# Kilde
assert out.get('source') == 'rust_binding'

# repr_kind kan være på toppnivå eller i debug, og kan være 'OBJECT'/'object'
rk = out.get('repr_kind') or (out.get('debug') or {}).get('repr_kind')
assert isinstance(rk, str) and rk.lower() == 'object'

# used_fallback kan være på toppnivå eller i debug
uf = out.get('used_fallback')
if uf is None:
    uf = (out.get('debug') or {}).get('used_fallback')
assert uf is False

print('OK: rust_binding / OBJECT / used_fallback=false')
