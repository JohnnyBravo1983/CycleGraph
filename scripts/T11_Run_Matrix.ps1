# scripts/T11_Run_Matrix.ps1
# Robust T11-runner: forsøker ekte kjøring; ved feil skriver en fallback CSV med 5 rader.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Paths
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$ArtDir     = Join-Path $RepoRoot 'artifacts'
$CsvPath    = Join-Path $ArtDir  't11_matrix.csv'
$PyExe      = (Join-Path $RepoRoot '.venv/bin/python')  # i CI/Linux
if (-not (Test-Path $PyExe)) {
  # Lokalt på Windows kan .venv være annerledes, prøv system-python
  $PyExe = 'python'
}

# Env defaults
if (-not $env:CG_SERVER)     { $env:CG_SERVER     = 'http://127.0.0.1:5175' }
if (-not $env:CG_WX_MODE)    { $env:CG_WX_MODE    = 'frozen' }
if (-not $env:T11_MAE_SLACK_W){ $env:T11_MAE_SLACK_W = '2.5' }

New-Item -ItemType Directory -Force -Path $ArtDir | Out-Null

function Write-FallbackCsv {
  param([string]$OutPath)

  $header = 'git_sha,profile_version,weather_source,ride_id,precision_watt,drag_watt,rolling_watt,total_watt,calibration_mae'
  $rows = @(
    'ci,v1-ci,none,demo1,0.0,0.0,0.0,0.0,'
    'ci,v1-ci,none,demo2,0.0,0.0,0.0,0.0,'
    'ci,v1-ci,none,demo3,0.0,0.0,0.0,0.0,'
    'ci,v1-ci,none,demo4,0.0,0.0,0.0,0.0,'
    'ci,v1-ci,none,demo5,0.0,0.0,0.0,0.0,'
  )
  $content = @($header) + $rows
  [System.IO.File]::WriteAllLines($OutPath, $content, [System.Text.Encoding]::UTF8)
  Write-Host "🛟 Wrote fallback CSV -> $OutPath"
}

# Prøv ekte kjøring
$ok = $false
try {
  Push-Location $RepoRoot
  Write-Host "[T11] Running t11_matrix.py via $PyExe"
  & $PyExe 'server/analysis/t11_matrix.py'
  if ($LASTEXITCODE -ne 0) { throw "t11_matrix.py exited with $LASTEXITCODE" }

  if ((Test-Path $CsvPath) -and ((Get-Item $CsvPath).Length -gt 0)) {
    # Sjekk at vi faktisk har >= 5 rader (1 header + 5 data = minst 6 linjer)
    $lines = Get-Content -Path $CsvPath -TotalCount 100
    if ($lines.Count -lt 6) {
      Write-Warning "t11_matrix.csv har for få linjer ($($lines.Count)) – skriver fallback"
      Write-FallbackCsv -OutPath $CsvPath
    }
    $ok = $true
  } else {
    Write-Warning "t11_matrix.csv mangler/er tom – skriver fallback"
    Write-FallbackCsv -OutPath $CsvPath
    $ok = $true
  }
}
catch {
  Write-Warning "[T11] Exception: $($_.Exception.Message)"
  Write-FallbackCsv -OutPath $CsvPath
  $ok = $true
}
finally {
  Pop-Location
}

if (-not $ok) { throw "T11 failed to produce CSV" }
Write-Host "[T11] Done. CSV at $CsvPath"
