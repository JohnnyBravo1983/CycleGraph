param([switch]$Clean)

$ErrorActionPreference = "Stop"

# --- Finn repo-roten robust ---
# Når scriptet kjøres fra fil, bruk PSScriptRoot. Ellers bruk gjeldende dir.
if ($PSScriptRoot) {
  $scriptDir = $PSScriptRoot
} else {
  $scriptDir = Get-Location
}
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

# Sanity: må ha core/Cargo.toml
$corePath = Join-Path $repoRoot "core"
$cargoToml = Join-Path $corePath "Cargo.toml"
if (!(Test-Path $cargoToml)) {
  throw "Fant ikke core/Cargo.toml under $repoRoot . Kjør scriptet fra CycleGraph-repoet (eller plasser det i scripts/)."
}

# 1) Venv
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  py -3.12 -m venv .venv
}

# 2) Aktiver venv
.\.venv\Scripts\Activate.ps1

# 3) Herd miljø
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONPATH = $repoRoot.Path

# 4) Rydd ev. gamle wheel/pyd i denne venv-en
pip uninstall -y cyclegraph_core cyclegraph-core | Out-Null

# 5) Bygg Rust-modulen utenfor OneDrive
$env:CARGO_TARGET_DIR = "C:\cg-build"
Push-Location $corePath
if ($Clean) { cargo clean }

# Viktig: bygg med riktige features (utvid her hvis du har flere feature-gates)
# -F "python" holder ofte, men enkelte funksjoner hos deg er bak andre flagg.
# Prøv først med disse vanlige:
$maturinFeatures = 'python,wind,calibration'
maturin develop --release --features "$maturinFeatures"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "maturin build feilet" }
Pop-Location

# 6) Verifiser lastet modul & exports
@'
import sys, cyclegraph_core as cg
print("PY:", sys.executable)
print("MOD:", cg.__file__)
need = ("analyze_session", "compute_power", "compute_power_with_wind_json", "rust_calibrate_session")
missing = [n for n in need if not hasattr(cg, n)]
print("MISSING:", missing)
'@ | python -

Write-Host "`nMiljø klart. Kjør: pytest -q" -ForegroundColor Green
