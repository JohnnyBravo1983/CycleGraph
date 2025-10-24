param([int]$Port = 5175)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Finn repo-roten
$cwd = (Get-Location).Path
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $cwd }
function Find-RepoRoot([string]$start) {
    $d = Get-Item -LiteralPath $start
    while ($null -ne $d) {
        $hasApp = Test-Path (Join-Path $d.FullName 'app.py')
        $hasPkg = Test-Path (Join-Path $d.FullName 'cyclegraph')
        if ($hasApp -or $hasPkg) { return $d.FullName }
        $parent = Split-Path -Parent $d.FullName
        if (-not $parent -or $parent -eq $d.FullName) { break }
        $d = Get-Item -LiteralPath $parent
    }
    return $start
}
$repoRoot = Find-RepoRoot $scriptDir
Set-Location $repoRoot

# Velg python
$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

# Last .env
$envPath = Join-Path $repoRoot '.env'
if (Test-Path $envPath) {
  Get-Content $envPath | % {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $kv = $line -split '=', 2
    if ($kv.Count -eq 2) {
      $k = $kv[0].Trim(); $v = $kv[1].Trim().Trim("'",'"')
      if ($k) { Set-Item -Path ("Env:{0}" -f $k) -Value $v }
    }
  }
}

if (-not $env:CG_PUBLISH_TOGGLE) { $env:CG_PUBLISH_TOGGLE = 'true' }
$env:PYTHONPATH = $repoRoot

# Finn første ledige port fra $Port til $Port+20
function Test-PortFree([int]$p) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  return -not $c
}
$chosen = $null
for ($p=$Port; $p -le $Port+20; $p++) {
  if (Test-PortFree $p) { $chosen = $p; break }
}
if (-not $chosen) { throw "Fant ingen ledig port i området $Port-$($Port+20)" }

Write-Host "[CycleGraph] Repo ............ $repoRoot"
Write-Host "[CycleGraph] Python .......... $py"
Write-Host "[CycleGraph] PYTHONPATH ...... $env:PYTHONPATH"
Write-Host "[CycleGraph] CG_PUBLISH_TOGGLE = $env:CG_PUBLISH_TOGGLE"
Write-Host "[CycleGraph] STRAVA_ACCESS_TOKEN set? " ([bool]$env:STRAVA_ACCESS_TOKEN)
Write-Host "[CycleGraph] Starter på port  .. $chosen"

# Import-sjekk
& $py -c "import sys; print('Python', sys.version); import uvicorn, fastapi; import app; print('Uvicorn/FASTAPI OK; app import OK')" 2>$null

# Start uten reload (én prosess)
& $py -m uvicorn app:app --host 127.0.0.1 --port $chosen
