param(
  [string] $Sid     = "ride3",
  [int]    $Port    = 5179,
  [string] $ApiHost = "127.0.0.1"
)

# ===== Enkelt analyze-test (uten vær) =====
$BASE   = "http://$($ApiHost):$Port"
$logDir = "logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outCsv   = Join-Path $logDir "analyze_run_$runStamp.csv"

function Get-Persist {
  param([string]$sid)
  $path = ".\data\sessions\$sid.json"
  if (Test-Path $path) {
    try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
  }
  return $null
}

function Call-AnalyzeDefaults {
  try {
    $resp = Invoke-RestMethod -Method Post -Uri "$($BASE)/api/sessions/$Sid/analyze" `
      -ContentType "application/json" -Body "{}" -TimeoutSec 60
  } catch { $resp = $null }

  $persist = Get-Persist -sid $Sid
  $pw = if ($resp -and $resp.precision_watt) { $resp.precision_watt } elseif ($persist) { $persist.precision_watt } else { $null }
  $ci = if ($resp -and $resp.precision_watt_ci) { $resp.precision_watt_ci } elseif ($persist) { $persist.precision_watt_ci } else { $null }
  $prof = if ($resp -and $resp.profile) { $resp.profile } elseif ($persist) { $persist.profile } else { $null }

  [pscustomobject]@{
    ts   = (Get-Date).ToString("s")
    sid  = $Sid
    in_CdA = $null; in_Crr = $null; in_weight_kg = $null; in_device = $null
    pw   = $pw
    ci   = $ci
    prof_CdA = $(if($prof){ $prof.CdA } else { $null })
    prof_Crr = $(if($prof){ $prof.Crr } else { $null })
    prof_w_kg = $(if($prof){ $prof.weight_kg } else { $null })
    prof_device = $(if($prof){ $prof.device } else { $null })
  }
}

function Call-Analyze {
  param([double]$CdA,[double]$Crr,[double]$WeightKg,[string]$Device="strava")

  $body = @{ profile = @{ CdA=$CdA; Crr=$Crr; weight_kg=$WeightKg; device=$Device } } | ConvertTo-Json
  try {
    $resp = Invoke-RestMethod -Method Post -Uri "$($BASE)/api/sessions/$Sid/analyze" `
      -ContentType "application/json" -Body $body -TimeoutSec 60
  } catch { $resp = $null }

  $persist = Get-Persist -sid $Sid
  $pw = if ($resp -and $resp.precision_watt) { $resp.precision_watt } elseif ($persist) { $persist.precision_watt } else { $null }
  $ci = if ($resp -and $resp.precision_watt_ci) { $resp.precision_watt_ci } elseif ($persist) { $persist.precision_watt_ci } else { $null }
  $prof = if ($resp -and $resp.profile) { $resp.profile } elseif ($persist) { $persist.profile } else { $null }

  [pscustomobject]@{
    ts   = (Get-Date).ToString("s")
    sid  = $Sid
    in_CdA = $CdA; in_Crr = $Crr; in_weight_kg = $WeightKg; in_device = $Device
    pw   = $pw
    ci   = $ci
    prof_CdA = $(if($prof){ $prof.CdA } else { $null })
    prof_Crr = $(if($prof){ $prof.Crr } else { $null })
    prof_w_kg = $(if($prof){ $prof.weight_kg } else { $null })
    prof_device = $(if($prof){ $prof.device } else { $null })
  }
}

Write-Host "== Analyze-test start $(Get-Date -Format T) ==" -ForegroundColor Cyan

# 1) baseline (defaults)
$baseline = Call-AnalyzeDefaults
if (-not $baseline) { throw "Baseline feilet mot $($BASE)" }

# 2) cases (juster fritt)
$cases = @(
  @{ CdA=0.28; Crr=0.004; WeightKg=78.0; Device="strava" }
  @{ CdA=0.30; Crr=0.005; WeightKg=82.0; Device="zwift"  }
  @{ CdA=0.32; Crr=0.004; WeightKg=78.0; Device="garmin" }
  @{ CdA=0.28; Crr=0.006; WeightKg=78.0; Device="strava" }
  @{ CdA=0.28; Crr=0.004; WeightKg=90.0; Device="strava" }
)

# 3) kjør
$results = @()
$results += $baseline
foreach ($c in $cases) {
  $results += Call-Analyze -CdA $c.CdA -Crr $c.Crr -WeightKg $c.WeightKg -Device $c.Device
}

# 4) vis og lagre
Write-Host "`n-- Resultater --" -ForegroundColor Yellow
$results | Select-Object ts,sid,in_CdA,in_Crr,in_weight_kg,in_device,pw,ci,prof_CdA,prof_Crr,prof_w_kg,prof_device `
         | Format-Table -AutoSize

$results | Export-Csv -NoTypeInformation -Delimiter ";" -Path $outCsv
Write-Host "`nCSV: $outCsv" -ForegroundColor Green
Write-Host "`n== Ferdig ==" -ForegroundColor Cyan
