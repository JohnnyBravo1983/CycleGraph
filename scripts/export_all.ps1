# scripts/export_all.ps1
# Trinn 13 – Export & Final Lock
# Kjør fra repo-rot. Skriver til export/<YYYYMMDD>/
# Krever aktiv .venv og bygget core (maturin develop --release -F python)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "[T13] Determinisme-guards" -ForegroundColor Cyan
$env:TZ              = "UTC"
$env:LANG            = "C"
$env:LC_ALL          = "C"
$env:PYTHONHASHSEED  = "0"

# Vær skal allerede være "frozen" i upstream analyser, men hint beholdes for manifest
$env:CG_WX_MODE = "frozen"

# Sett Python-binær eksplisitt hvis nødvendig
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# Sørg for export/ finnes
if (-not (Test-Path "export")) {
  New-Item -ItemType Directory -Path "export" | Out-Null
}

Write-Host "[T13] Exporter kjører..." -ForegroundColor Cyan
& $python -m server.analysis.export13 --out "export" --frozen
if ($LASTEXITCODE -ne 0) {
  throw "Export script failed with code $LASTEXITCODE"
}

# --- Patch 6: velg nyeste datomappe deterministisk (^\d{8}$) ---
Write-Host "[T13] Slår opp nyeste datomappe..." -ForegroundColor Cyan
# Velg nyeste datomappe deterministisk (^\d{8}$)
$dirs = Get-ChildItem -Directory export | Where-Object { $_.Name -match '^\d{8}$' } | Sort-Object Name
if (-not $dirs -or @($dirs).Count -eq 0) {
    throw "Ingen eksportmapper i ./export"
}
$latest = (@($dirs))[-1].FullName
Write-Host "[EXPORT13] Valgt mappe: $latest"

# Gjør det enkelt for Tr14 å finne riktig mappe:
# 1) Sett env-vars i denne prosessen (kan hentes av Tr14 hvis trigget i samme session)
$env:CG_EXPORT_LATEST      = (Get-Item $latest).Name
$env:CG_EXPORT_LATEST_PATH = $latest

# 2) Skriv markørfiler som kan leses uavhengig av prosess
Set-Content -Path "export\latest.txt" -Value (Get-Item $latest).Name -Encoding ascii

$manifest = [ordered]@{
  latest          = (Get-Item $latest).Name
  path            = $latest
  generated_utc   = (Get-Date).ToUniversalTime().ToString("s") + "Z"
  wx_mode_hint    = $env:CG_WX_MODE
  python_exe      = (Get-Command $python).Source
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path "export\latest.json" -Encoding utf8

Write-Host "[T13] Ferdig: $latest" -ForegroundColor Green
Write-Host "Tips: Tr14 kan lese 'export\latest.txt' eller 'export\latest.json', eller bruke env CG_EXPORT_LATEST_PATH." -ForegroundColor DarkCyan