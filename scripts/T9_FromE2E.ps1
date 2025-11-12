Param(
  [string]$E2E = "scripts\E2E.Multiple_Rides.ps1",
  [string]$TargetRoot = "logs\actual10"
)

$ErrorActionPreference = "Stop"

# 1) Kjør E2E inne i scripts\
Push-Location "scripts"
try {
  Write-Host "[T9] Running E2E.Multiple_Rides.ps1 inside scripts\ ..."
  & ".\E2E.Multiple_Rides.ps1"
} finally {
  Pop-Location
}

# 2) Kopier scripts\_debug -> logs\actual10\<timestamp> + latest
$src = "scripts\_debug"
if (-not (Test-Path $src)) {
  Write-Error "[T9] Expected E2E output at $src but not found."
  exit 2
}
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$dstTs = Join-Path $TargetRoot $ts
$dstLatest = Join-Path $TargetRoot "latest"

New-Item -ItemType Directory -Force -Path $dstTs     | Out-Null
New-Item -ItemType Directory -Force -Path $dstLatest | Out-Null

Copy-Item -Path "$src\*" -Destination $dstTs -Recurse -Force
Remove-Item -Path "$dstLatest\*" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$src\*" -Destination $dstLatest -Recurse -Force

Write-Host "[T9] Copied E2E outputs to:"
Write-Host ("     {0}" -f $dstTs)
Write-Host ("     {0}" -f $dstLatest)

# 3) Kjør trendmotoren på latest
python scripts/T9_Trend_Run.py --log-dir "$dstLatest" --out-dir "$dstLatest" 2>&1 | Tee-Object -FilePath (Join-Path $dstLatest "trinn9_run_stdout.txt")

# 4) Minimumsartefakter
$required = @(
  (Join-Path $dstLatest "trinn9_trend_summary.csv"),
  (Join-Path $dstLatest "trinn9_anomalies.csv")
)
$missing = @()
foreach ($f in $required) { if (-not (Test-Path $f)) { $missing += $f } }
if ($missing.Count -gt 0) {
  Write-Error ("[T9] Missing: {0}" -f ($missing -join ', '))
  exit 2
}

Write-Host ("[T9] OK. Generated artifacts in {0}:" -f $dstLatest)
Get-ChildItem $dstLatest | Where-Object { $_.Name -like "trinn9_*" } | Select-Object Name,Length,LastWriteTime
