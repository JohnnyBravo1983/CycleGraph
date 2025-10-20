param([switch]$Clean)

# Gå til repo-roten (scripts\..)
Set-Location $PSScriptRoot\..

# 1) Sørg for venv
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  py -3.12 -m venv .venv
}

# 2) Aktiver korrekt venv
.\.venv\Scripts\Activate.ps1

# 3) Herd miljøet mot "feil venv" / user-site
$env:PYTHONNOUSERSITE = "1"     # ignorer brukerens site-packages
$env:PYTHONPATH = (Get-Location).Path  # repo-roten først på sys.path
[Environment]::SetEnvironmentVariable("PYTHONNOUSERSITE","1","Process")

# 4) Rydd ev. feil installasjoner i denne venv-en
pip uninstall -y cyclegraph_core cyclegraph-core | Out-Null

# 5) Bygg Rust-modulen til *utenfor* OneDrive
$env:CARGO_TARGET_DIR = "C:\cg-build"
Push-Location core
if ($Clean) { cargo clean }
maturin develop --release -F python
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "maturin build feilet" }
Pop-Location

# 6) Verifiser at riktig modul+python lastes (bruk here-string -> python -)
@'
import sys, cyclegraph_core as cg
print("PY:", sys.executable)
print("MOD:", cg.__file__)
print("EXPORTS:", [x for x in dir(cg) if any(k in x for k in ("analy","compute_power","calibrate"))])
'@ | python -

Write-Host "`nMiljø klart. Kjør: pytest -q" -ForegroundColor Green
