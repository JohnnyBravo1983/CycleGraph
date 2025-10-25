param(
  [string] $TrinnName     = "trinnX",
  [string] $SidBase       = "ride",
  [int]    $Port          = 5179,
  [string] $ApiHost       = "127.0.0.1",
  [switch] $IncludeWeather,          # Slås på fra og med trinn 4
  [switch] $UniqueSidPerCase = $true,# Unik sid per testcase gir “kald start” hver gang
  [switch] $ClearPersistBeforeCase,  # Alternativ til UniqueSidPerCase
  [string] $CasesPath,               # Valgfritt: JSON-fil med cases [{CdA,Crr,WeightKg,Device}]
  [string] $OutDir        = "logs"
)

# ====== Init ======
$BASE = "http://$($ApiHost):$Port"
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$outCsv = Join-Path $OutDir "$TrinnName-analyze_$stamp.csv"

# Fast kolonnerekkefølge (stabil CSV mellom trinn)
$CsvColumns = @(
  'ts','trinn','sid',
  'in_CdA','in_Crr','in_weight_kg','in_device',
  'pw','ci',
  'prof_CdA','prof_Crr','prof_w_kg','prof_device',
  'weather_applied' # blir $null i trinn uten vær
)

function Get-Persist([string]$sid){
  $p = ".\data\sessions\$sid.json"
  if (Test-Path $p) { try { return Get-Content $p -Raw | ConvertFrom-Json } catch { return $null } }
  return $null
}

function Post-Analyze([string]$sid, [hashtable]$profile, [switch]$defaults){
  $uri = "$($BASE)/api/sessions/$sid/analyze"
  $body = if ($defaults) { "{}" } else { @{ profile=$profile } | ConvertTo-Json -Depth 6 }

  try {
    return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json" -Body $body -TimeoutSec 60
  } catch { return $null }
}

function Build-Row([string]$sid, $resp, $persist, $inputs, [switch]$IncludeWeather){
  $prof = if ($resp -and $resp.profile) { $resp.profile } elseif ($persist -and $persist.profile) { $persist.profile } else { $null }
  $pw   = if ($resp -and $resp.precision_watt)     { $resp.precision_watt }     elseif ($persist) { $persist.precision_watt }     else { $null }
  $ci   = if ($resp -and $resp.precision_watt_ci)  { $resp.precision_watt_ci }  elseif ($persist) { $persist.precision_watt_ci }  else { $null }
  $wapp = if ($IncludeWeather) {
            if ($resp -ne $null -and $resp.PSObject.Properties.Name -contains 'weather_applied') { [bool]$resp.weather_applied }
            elseif ($persist -ne $null -and $persist.PSObject.Properties.Name -contains 'weather_applied') { [bool]$persist.weather_applied }
            else { $null }
          } else { $null }

  [pscustomobject]@{
    ts              = (Get-Date).ToString("s")
    trinn           = $TrinnName
    sid             = $sid
    in_CdA          = $inputs.CdA
    in_Crr          = $inputs.Crr
    in_weight_kg    = $inputs.WeightKg
    in_device       = $inputs.Device
    pw              = $pw
    ci              = $ci
    prof_CdA        = $(if($prof){ $prof.CdA } else { $null })
    prof_Crr        = $(if($prof){ $prof.Crr } else { $null })
    prof_w_kg       = $(if($prof){ $prof.weight_kg } else { $null })
    prof_device     = $(if($prof){ $prof.device } else { $null })
    weather_applied = $wapp
  }
}

Write-Host "== $TrinnName – analyze test $(Get-Date -Format T) ==" -ForegroundColor Cyan

# ====== Cases ======
if ($CasesPath -and (Test-Path $CasesPath)) {
  try {
    $cases = Get-Content $CasesPath -Raw | ConvertFrom-Json
  } catch { throw "Kunne ikke lese cases fra $($CasesPath): $($_.Exception.Message)" }
} else {
  # Standard cases – endres sjelden fra trinn til trinn
  $cases = @(
    @{ CdA=0.28; Crr=0.004; WeightKg=78.0; Device="strava" }
    @{ CdA=0.30; Crr=0.005; WeightKg=82.0; Device="zwift"  }
    @{ CdA=0.32; Crr=0.004; WeightKg=78.0; Device="garmin" }
    @{ CdA=0.28; Crr=0.006; WeightKg=78.0; Device="strava" }
    @{ CdA=0.28; Crr=0.004; WeightKg=90.0; Device="strava" }
  )
}

# ====== Baseline ======
$baselineSid = "$SidBase"
$resp0    = Post-Analyze -sid $baselineSid -defaults
$persist0 = Get-Persist $baselineSid
$rows = @()
$rows += Build-Row -sid $baselineSid -resp $resp0 -persist $persist0 -inputs @{CdA=$null;Crr=$null;WeightKg=$null;Device=$null} -IncludeWeather:$IncludeWeather

# ====== Run cases ======
$idx = 1
foreach ($c in $cases) {
  $sidCase = if ($UniqueSidPerCase) { "{0}-c{1:00}" -f $SidBase, $idx } else { $SidBase }
  if ($ClearPersistBeforeCase -and -not $UniqueSidPerCase) {
    $persistPath = ".\data\sessions\$sidCase.json"
    Remove-Item $persistPath -ErrorAction SilentlyContinue
  }

  $profile = @{ CdA=$c.CdA; Crr=$c.Crr; weight_kg=$c.WeightKg; device=$c.Device }
  $resp    = Post-Analyze -sid $sidCase -profile $profile
  $persist = Get-Persist $sidCase
  $rows   += Build-Row -sid $sidCase -resp $resp -persist $persist -inputs $c -IncludeWeather:$IncludeWeather
  $idx++
}

# ====== Output ======
Write-Host "`n-- Resultater ($TrinnName) --" -ForegroundColor Yellow
$rows | Select-Object $CsvColumns | Format-Table -AutoSize

$rows | Select-Object $CsvColumns | Export-Csv -NoTypeInformation -Delimiter ";" -Path $outCsv
Write-Host "`nCSV: $outCsv" -ForegroundColor Green

Write-Host "`n== Ferdig ==" -ForegroundColor Cyan
