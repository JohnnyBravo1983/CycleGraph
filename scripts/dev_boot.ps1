param([switch]$Clean)
Set-Location $PSScriptRoot\..
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) { py -3.12 -m venv .venv }
.\.venv\Scripts\Activate.ps1
$env:CARGO_TARGET_DIR = "C:\cg-build"
if ($Clean) { Push-Location core; cargo clean; Pop-Location }
Push-Location core
maturin develop --release -F python
if ($LASTEXITCODE -ne 0) { Write-Error "maturin build feilet"; Pop-Location; exit 1 }
Pop-Location
python - << 'PY'
import cyclegraph_core as cg
exports = [x for x in dir(cg) if any(k in x for k in ("analy", "compute_power", "calibrate"))]
print("OK exports:", exports)
PY
Write-Host "`nMiljÃ¸ klart. KjÃ¸r: python -m pytest -q" -ForegroundColor Green
