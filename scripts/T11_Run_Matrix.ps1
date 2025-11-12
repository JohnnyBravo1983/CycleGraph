# scripts/T11_Run_Matrix.ps1
param(
  [string]$ServerUrl = "http://127.0.0.1:5175",
  [switch]$Frozen,
  [switch]$BootstrapBaseline
)

$ErrorActionPreference = "Stop"
$env:PYTHONHASHSEED = "0"
$env:LANG = "C"
$env:TZ = "UTC"

function Test-Server($url) {
  try {
    (Invoke-WebRequest -Uri "$url/api/profile/get" -TimeoutSec 2 -UseBasicParsing) | Out-Null
    return $true
  } catch { return $false }
}

# trekk ut port til uvicorn-oppstart
$uri = [System.Uri]$ServerUrl
$port = if ($uri.Port) { $uri.Port } else { 5175 }

$serverStarted = $false
if (-not (Test-Server $ServerUrl)) {
  Write-Host "[T11] starting uvicorn app:app on port $port ..."
  Start-Process -WindowStyle Hidden -FilePath "python" -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","$port" -PassThru | Out-Null
  $serverStarted = $true
  Start-Sleep -Seconds 2
}

$tries = 20
while ($tries -gt 0 -and -not (Test-Server $ServerUrl)) {
  Start-Sleep -Milliseconds 500
  $tries--
}
if ($tries -le 0) { throw "Server did not come up at $ServerUrl" }

$env:CG_SERVER = $ServerUrl
$env:CG_WX_MODE = $(if ($Frozen) { "frozen" } else { "real" })
$env:T11_ALLOW_BOOTSTRAP = $(if ($BootstrapBaseline) { "1" } else { "0" })
$env:T11_MAE_SLACK_W = "2.5"

python -m server.analysis.t11_matrix | Tee-Object -Variable _log

Write-Host "[T11] Done. Artifacts:"
Get-ChildItem artifacts -File

if ($serverStarted) {
  Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
