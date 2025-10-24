param(
  [int]$Port = 5179
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here '..\..') | % Path
Set-Location $repo

Write-Host "[CycleGraph] Repo ............ $repo"
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (!(Test-Path $py)) { throw ".venv mangler. Aktiver/installer venv først." }
Write-Host "[CycleGraph] Python .......... $py"
Write-Host "[CycleGraph] PYTHONPATH ...... $repo"

# Vis nyttige env
$env:PYTHONPATH = $repo
# Les .env i prosessen (for logging)
try {
  & $py -c "from dotenv import load_dotenv; load_dotenv(); import os; print('STRAVA_ACCESS_TOKEN set? ', bool(os.getenv('STRAVA_ACCESS_TOKEN')))"
} catch {}

# Frigjør port hvis opptatt
$inUse = (netstat -ano | findstr ":$Port") | Out-String
if ($inUse.Trim()) {
  Write-Host "[CycleGraph] Advarsel: Port $Port i bruk:`n$inUse"
  Write-Host "Kill prosess? (y/N)"
  $ans = Read-Host
  if ($ans -match '^[Yy]') {
    ($inUse -split "`n") | % {
      if ($_ -match '\s+LISTENING\s+(\d+)$') {
        $pid = $Matches[1]; taskkill /PID $pid /F | Out-Null
        Write-Host "Killed PID $pid"
      }
    }
  }
}

Write-Host "[CycleGraph] Starter på port  .. $Port"
# Kjør direkte for å få full traceback
& $py -m uvicorn app:app --host 127.0.0.1 --port $Port
