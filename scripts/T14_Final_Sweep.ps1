# scripts/T14_Final_Sweep.ps1
param(
  [string]$Server = $env:CG_SERVER,
  [string]$Date   = (Get-Date -Format "yyyyMMdd"),
  [switch]$StartServer
)

if (-not $Server) { $Server = "http://127.0.0.1:5175" }

# Determinisme
$env:TZ = "UTC"
$env:LANG = "C"
$env:LC_ALL = "C"
$env:PYTHONHASHSEED = "0"
$env:CG_WX_MODE = "frozen"        # <-- Final: frossent vær
$env:CG_T11_NO_WEATHER = ""       # <-- Final: vær SKAL brukes (ikke no_weather)

# (Valgfritt) start server
if ($StartServer) {
  Write-Host "[T14] Starter server på :5175 ..."
  Start-Process -NoNewWindow -FilePath python -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","5175" | Out-Null
  # enkel poll
  $ok = $false
  1..50 | ForEach-Object {
    try {
      $r = Invoke-RestMethod -Uri "$Server/api/profile/get" -Method GET -TimeoutSec 2
      if ($r.profile_version) { $ok = $true; return }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $ok) { throw "[T14] Server ikke klar innen tidsfrist." }
}

Write-Host "[T14] Final sweep (frozen) ..."
python -m server.analysis.final14 --server $Server --out-root export --date $Date --sweep --force

Write-Host "[T14] Export13 for dato $Date ..."
python -m server.analysis.export13 --date $Date

# sørg for at t11_matrix.csv ligger i dagens eksport (speiles for verifisering)
if (Test-Path "artifacts/t11_matrix.csv") {
  New-Item -ItemType Directory -Force -Path "export/$Date" | Out-Null
  Copy-Item "artifacts/t11_matrix.csv" "export/$Date/t11_matrix.csv" -Force
}

Write-Host "[T14] Verifikasjon og lås ..."
python -m server.analysis.final14 --server $Server --out-root export --date $Date --verify

Write-Host "[T14] Ferdig. Se: export/$Date/final14_manifest.json"
