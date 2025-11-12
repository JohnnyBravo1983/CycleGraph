# scripts/export_all.ps1
# Trinn 13 – Export & Final Lock
# Kjør fra repo-rot. Skriver til export/<YYYYMMDD>/
# Krever aktiv .venv og bygget core (maturin develop --release -F python)

$ErrorActionPreference = "Stop"

Write-Host "[T13] Determinisme-guards" -ForegroundColor Cyan
$env:TZ = "UTC"
$env:LANG = "C"
$env:LC_ALL = "C"
$env:PYTHONHASHSEED = "0"

# Vær skal allerede være "frozen" i upstream analyser, men hint beholdes for manifest
$env:CG_WX_MODE = "frozen"

# Sett Python-binære eksplisitt hvis nødvendig
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "[T13] Exporter kjører..." -ForegroundColor Cyan
& $python -m server.analysis.export13 --out "export" --frozen

if ($LASTEXITCODE -ne 0) {
  throw "Export script failed with code $LASTEXITCODE"
}

# Finn nyeste DATO-mappe under export\
$latest = Get-ChildItem export -Directory |
  Where-Object { $_.Name -match '^\d{8}$' } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $latest) {
  throw "No dated export folder found (expected export\<YYYYMMDD>)"
}

Write-Host "[T13] Ferdig: $($latest.FullName)" -ForegroundColor Green
