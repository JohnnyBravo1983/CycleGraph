param(
  [string] $SidBase = "ride3",
  [int]    $Port    = 5177,
  [string] $ApiHost = "127.0.0.1",
  [string] $OutDir  = "logs",
  [string] $CasesPath
)

$BASE   = ('http://{0}:{1}' -f $ApiHost, $Port)
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$outCsv = Join-Path $OutDir ("trinn3-analyze_{0}.csv" -f $stamp)

$CsvColumns = @('ts','sid','in_CdA','in_Crr','in_weight_kg','in_device','pw','ci','prof_CdA','prof_Crr','prof_w_kg','prof_device')

function Get-Persist([string]$sid){
  $p = ".\data\sessions\$sid.json"
  if (Test-Path $p) { try { return Get-Content $p -Raw | ConvertFrom-Json } catch { return $null } }
  return $null
}

function Save-Persist([string]$sid, $obj){
  $p = ".\data\sessions\$sid.json"
  $obj | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $p -Encoding UTF8
}

function Post-Analyze([string]$sid, [hashtable]$profile, [switch]$defaults){
  $uri  = ('{0}/api/sessions/{1}/analyze' -f $BASE, $sid)
  $body = if ($defaults) { "{}" } else { @{ profile = $profile } | ConvertTo-Json -Depth 6 }
  try { return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body $body -TimeoutSec 60 }
  catch { return $null }
}

function Build-Row([string]$sid, $resp, $persist, $inputs){
  $prof = if ($resp -and $resp.profile) { $resp.profile } elseif ($persist -and $persist.profile){ $persist.profile } else { $null }
  $pw   = if ($resp -and $resp.precision_watt)    { $resp.precision_watt }    elseif ($persist){ $persist.precision_watt }    else { $null }
  $ci   = if ($resp -and $resp.precision_watt_ci) { $resp.precision_watt_ci } elseif ($persist){ $persist.precision_watt_ci } else { $null }

  [pscustomobject]@{
    ts           = (Get-Date).ToString("s")
    sid          = $sid
    in_CdA       = $inputs.CdA
    in_Crr       = $inputs.Crr
    in_weight_kg = $inputs.WeightKg
    in_device    = $inputs.Device
    pw           = $pw
    ci           = $ci
    prof_CdA     = $(if($prof){ $prof.CdA } else { $null })
    prof_Crr     = $(if($prof){ $prof.Crr } else { $null })
    prof_w_kg    = $(if($prof){ $prof.weight_kg } else { $null })
    prof_device  = $(if($prof){ $prof.device } else { $null })
  }
}

Write-Host ("== Trinn 3 – analyze test {0} ==" -f (Get-Date -Format T)) -ForegroundColor Cyan

# 1) Cases
if ($CasesPath -and (Test-Path $CasesPath)) {
  try { $cases = Get-Content $CasesPath -Raw | ConvertFrom-Json }
  catch { throw ("Kunne ikke lese cases fra fil [{0}] - {1}" -f $CasesPath, $_.Exception.Message) }
} else {
  $cases = @(
    @{ CdA=0.28; Crr=0.004; WeightKg=78.0; Device="strava" }
    @{ CdA=0.30; Crr=0.005; WeightKg=82.0; Device="zwift"  }
    @{ CdA=0.32; Crr=0.004; WeightKg=78.0; Device="garmin" }
    @{ CdA=0.28; Crr=0.006; WeightKg=78.0; Device="strava" }
    @{ CdA=0.28; Crr=0.004; WeightKg=90.0; Device="strava" }
  )
}

# 2) Baseline på $SidBase – sørger for at ride3.json finnes/oppdateres
$resp0    = Post-Analyze -sid $SidBase -defaults
$persist0 = Get-Persist $SidBase

# 3) Seed per case: kopier baseline.json, men NØKKEL: fjern lagret profile + PW/CI
$baselineFile = ".\data\sessions\$SidBase.json"
if (!(Test-Path $baselineFile)) { throw "Finner ikke baseline-fil: $baselineFile. Kjør skriptet på nytt når serveren har skrevet den." }

$rows = @()
$rows += Build-Row -sid $SidBase -resp $resp0 -persist $persist0 -inputs @{CdA=$null;Crr=$null;WeightKg=$null;Device=$null}

$idx = 1
foreach ($c in $cases) {
  $sidCase  = ('{0}-c{1:d2}' -f $SidBase, $idx)
  $persistClone = Get-Persist $SidBase
  if ($persistClone) {
    # Stripp bort profile + precision for at API skal bruke innsendt profil og regne på nytt
    $persistClone.PSObject.Properties.Remove('profile') | Out-Null
    $persistClone.PSObject.Properties.Remove('precision_watt') | Out-Null
    $persistClone.PSObject.Properties.Remove('precision_watt_ci') | Out-Null
    Save-Persist -sid $sidCase -obj $persistClone
  } else {
    Copy-Item $baselineFile ".\data\sessions\$sidCase.json" -Force
  }

  $resp    = Post-Analyze -sid $sidCase -profile @{ CdA=$c.CdA; Crr=$c.Crr; weight_kg=$c.WeightKg; device=$c.Device }
  $persist = Get-Persist $sidCase
  $rows   += Build-Row -sid $sidCase -resp $resp -persist $persist -inputs $c
  $idx++
}

# 4) Vis & lagre
Write-Host "`n-- Resultater (Trinn 3) --" -ForegroundColor Yellow
$rows | Select-Object $CsvColumns | Format-Table -AutoSize

$rows | Select-Object $CsvColumns | Export-Csv -NoTypeInformation -Delimiter ";" -Path $outCsv
Write-Host ("`nCSV skrevet: {0}" -f $outCsv) -ForegroundColor Green
Write-Host "`n== Ferdig ==" -ForegroundColor Cyan
