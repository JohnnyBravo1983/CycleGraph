# 0) Sørg for at du står i riktig repo
pwd  # skal ende på ...\CycleGraph

# 1) Venv
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) { py -3.12 -m venv .venv }
.\.venv\Scripts\Activate.ps1
$env:PYTHONNOUSERSITE="1"

# 2) Rydd opp i gammel installasjon / pyd
pip uninstall -y cyclegraph_core cyclegraph-core | Out-Null

# 3) Fjern gamle bygg-artifakter (ren start)
$env:CARGO_TARGET_DIR="C:\cg-build"
if (Test-Path $env:CARGO_TARGET_DIR) { Remove-Item -Recurse -Force $env:CARGO_TARGET_DIR }
if (Test-Path .\core\target)        { Remove-Item -Recurse -Force .\core\target }

# 4) Bygg kun med python-feature (ikke be om features som ikke finnes)
Push-Location core
cargo clean
maturin develop --release -F python
Pop-Location

# 5) Verifiser at modulen og symbolene finnes
$py = @'
import sys, cyclegraph_core as cg
print("PY:", sys.executable)
print("MOD:", cg.__file__)
need = ("analyze_session",)
print("MISSING:", [n for n in need if not hasattr(cg, n)])
'@
$py | python -

# 6) Kjør *én* test først
pytest -q core/tests/test_analyze_session.py::test_analyze_session_empty_arrays