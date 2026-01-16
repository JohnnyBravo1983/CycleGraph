param(
  [Parameter(Mandatory=$true)][string]$Uid,
  [int]$SampleN = 50
)

$ErrorActionPreference = "Stop"

$IDX = ".\state\users\$Uid\sessions_index.json"
if (-not (Test-Path $IDX)) { throw "Missing SSOT index: $IDX" }

# Detect result directory (prefer logs/results, fallback to repo-root)
$resultsDir = $null
if (Test-Path ".\logs\results") {
  $c = (Get-ChildItem ".\logs\results" -Filter "result_*.json" -File -ErrorAction SilentlyContinue | Measure-Object).Count
  if ($c -gt 0) { $resultsDir = ".\logs\results" }
}
if (-not $resultsDir) {
  $c = (Get-ChildItem "." -Filter "result_*.json" -File -ErrorAction SilentlyContinue | Measure-Object).Count
  if ($c -gt 0) { $resultsDir = "." }
}
if (-not $resultsDir) { throw "Could not find any result_*.json in .\\logs\\results or repo-root." }

$idxObj = Get-Content $IDX -Raw | ConvertFrom-Json

if (-not $idxObj.PSObject.Properties.Match("rides")) {
  throw "sessions_index.json does not contain a 'rides' array. Keys: $((($idxObj | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name) -join ', '))"
}

$rides = $idxObj.rides
if (-not $rides -or $rides.Count -eq 0) { throw "rides[] is empty for uid=$Uid" }

Write-Host "UID=$Uid"
Write-Host "SSOT index: $IDX"
Write-Host "Results dir: $resultsDir"
Write-Host "SSOT rides count = $($rides.Count)"

# sample
$sample = $rides | Select-Object -First $SampleN

function Get-TypeTag($obj, $prop) {
  $m = $obj.PSObject.Properties.Match($prop)
  if (-not $m) { return "MISSING" }
  $v = $obj.$prop
  if ($null -eq $v) { return "NULL" }
  return $v.GetType().FullName
}

# Build union of top-level keys
$keySet = @{}
$missingResults = New-Object System.Collections.Generic.List[string]

foreach ($rid in $sample) {
  $p = Join-Path $resultsDir "result_$rid.json"
  if (-not (Test-Path $p)) { $missingResults.Add([string]$rid); continue }
  $j = Get-Content $p -Raw | ConvertFrom-Json
  foreach ($k in ($j | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)) {
    $keySet[$k] = $true
  }
}

Write-Host "`nMissing result files (in sample): $($missingResults.Count)"
if ($missingResults.Count -gt 0) {
  $missingResults | Select-Object -First 20 | ForEach-Object { Write-Host "  - $_" }
}

$keyList = $keySet.Keys | Sort-Object
Write-Host "`nUnion of top-level result keys (sample):"
$keyList | ForEach-Object { Write-Host "  - $_" }

# Type map
$typeMap = @{}
foreach ($k in $keyList) { $typeMap[$k] = @{} }

foreach ($rid in $sample) {
  $p = Join-Path $resultsDir "result_$rid.json"
  if (Test-Path $p) {
    $j = Get-Content $p -Raw | ConvertFrom-Json
    foreach ($k in $keyList) {
      $t = Get-TypeTag $j $k
      $typeMap[$k][$t] = $true
    }
  }
}

Write-Host "`nMetrics with multiple observed types (RED FLAGS):"
$multi = foreach ($k in $keyList) {
  $types = $typeMap[$k].Keys
  if ($types.Count -gt 1) {
    [PSCustomObject]@{ metric=$k; types=($types -join " | ") }
  }
}
if (-not $multi) { Write-Host "  (none)" } else { $multi | Sort-Object metric | Format-Table -Auto }

Write-Host "`nTime/Date candidate fields:"
$keyList | Where-Object { $_ -match "time|date|start|end|ts|timestamp" } | ForEach-Object { Write-Host "  - $_" }


# --- METRICS SUBKEY INVENTORY (Task 1.4) ---
Write-Host "`nMETRICS subkey inventory (sample):"

$metricsKeySet = @{}
$metricsTypeMap = @{}

foreach ($rid in $sample) {
  $p = Join-Path $resultsDir "result_$rid.json"
  if (Test-Path $p) {
    $o = Get-Content $p -Raw | ConvertFrom-Json
    if ($o.PSObject.Properties.Match("metrics") -and $null -ne $o.metrics) {
      $mObj = $o.metrics
      $mKeys = $mObj | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name
      foreach ($mk in $mKeys) {
        $metricsKeySet[$mk] = $true
        if (-not $metricsTypeMap.ContainsKey($mk)) { $metricsTypeMap[$mk] = @{} }
        $v = $mObj.$mk
        $t = if ($null -eq $v) { "NULL" } else { $v.GetType().FullName }
        $metricsTypeMap[$mk][$t] = $true
      }
    }
  }
}

$metricsKeys = $metricsKeySet.Keys | Sort-Object
if (-not $metricsKeys -or $metricsKeys.Count -eq 0) {
  Write-Host "  (no metrics subkeys found in sample)"
} else {
  Write-Host "METRICS subkeys:"
  $metricsKeys | ForEach-Object { Write-Host "  - $_" }

  Write-Host "`nMETRICS subkeys with multiple observed types (RED FLAGS):"
  $mmulti = foreach ($k in $metricsKeys) {
    $types = $metricsTypeMap[$k].Keys
    if ($types.Count -gt 1) {
      [PSCustomObject]@{ metric=("metrics." + $k); types=($types -join " | ") }
    }
  }
  if (-not $mmulti) { Write-Host "  (none)" } else { $mmulti | Sort-Object metric | Format-Table -Auto }
}
# --- END METRICS SUBKEY INVENTORY ---


Write-Host "`nDone."


