param(
    [string] $Sid        = "local-mini",
    [long]   $ActivityId = 16333270450,
    [int]    $Port       = 5175,
    [string] $ApiHost    = "127.0.0.1",
    [double] $CdA        = 0.30,
    [double] $Crr        = 0.004,
    [double] $WeightKg   = 111.0,

    # Settes til $true for å sende kontrollert weather
    [bool]   $UseTestWeather = $true,
    [double] $WindMs         = 3.0,
    [double] $WindDir        = 270.0,
    [double] $AirTempC       = 12.0,
    [double] $AirPressHpa    = 1013.0
)

$ErrorActionPreference = "Stop"

function To-Rad([double]$deg) { [Math]::PI * $deg / 180.0 }
function Bearing-Deg([double]$lat1,[double]$lon1,[double]$lat2,[double]$lon2) {
    $p1 = To-Rad $lat1; $p2 = To-Rad $lat2
    $dl = To-Rad ($lon2 - $lon1)
    $y  = [Math]::Sin($dl) * [Math]::Cos($p2)
    $x  = [Math]::Cos($p1) * [Math]::Sin($p2) - [Math]::Sin($p1) * [Math]::Cos($p2) * [Math]::Cos($dl)
    $th = [Math]::Atan2($y, $x) * 180.0 / [Math]::PI
    if ($th -lt 0) { $th += 360.0 }
    return $th
}

$BASE   = ("http://{0}:{1}/api" -f $ApiHost, $Port)
$outDir = "debug_out"; if (!(Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

function Get-StravaStreams([long]$Id) {
    if (-not $env:STRAVA_ACCESS_TOKEN) { throw "STRAVA_ACCESS_TOKEN is not set" }
    $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
    $keys = "time,velocity_smooth,altitude,grade_smooth,latlng,moving"
    $u = "https://www.strava.com/api/v3/activities/$Id/streams?keys=$keys&key_by_type=true"
    Invoke-RestMethod -Method GET -Headers $h -Uri $u
}
function Get-StravaActivity([long]$Id) {
    if (-not $env:STRAVA_ACCESS_TOKEN) { throw "STRAVA_ACCESS_TOKEN is not set" }
    $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
    $u = "https://www.strava.com/api/v3/activities/$Id"
    Invoke-RestMethod -Method GET -Headers $h -Uri $u
}

Write-Host "== Trinn 4: verify heading + weather via analyze ==" -ForegroundColor Cyan

$act     = Get-StravaActivity $ActivityId
$streams = Get-StravaStreams  $ActivityId

$t  = @($streams.time.data)
$v  = @($streams.velocity_smooth.data)
$a  = @($streams.altitude.data)
$g  = @($streams.grade_smooth.data)
$ll = @($streams.latlng.data)
$mv = @($streams.moving.data)

$tc=$t.Count; $vc=$v.Count; $ac=$a.Count
$lc=($ll | ForEach-Object { $_ }) | Measure-Object | Select-Object -ExpandProperty Count
if (-not $lc) { $lc = 0 }

$n0 = [Math]::Min([Math]::Min($tc,$vc), $ac)
$n  = if ($lc -gt 0) { [Math]::Min($n0,$lc) } else { $n0 }
if ($n -le 1) { throw "Streams too short (n=$n)" }

# heading_deg per sample
$head = New-Object 'System.Collections.Generic.List[double]'
for ($i=0; $i -lt $n; $i++) {
    if ($i -lt ($n-1) -and $ll[$i] -ne $null -and $ll[$i+1] -ne $null) {
        $hdg = Bearing-Deg ([double]$ll[$i][0]) ([double]$ll[$i][1]) ([double]$ll[$i+1][0]) ([double]$ll[$i+1][1])
    } elseif ($i -gt 0) {
        $hdg = $head[$i-1]
    } else {
        $hdg = 0.0
    }
    $head.Add([double]$hdg)
}
if ($head.Count -ge 2) { $head[0] = $head[1] }
Write-Host ("[GPS] heading_deg computed for {0} samples" -f $head.Count) -ForegroundColor Green

# build samples
$samples = New-Object 'System.Collections.Generic.List[object]'
$stop = 0.5
for ($i=0; $i -lt $n; $i++) {
    $obj = @{
        t           = [double]$t[$i]
        v_ms        = [double]$v[$i]
        altitude_m  = [double]$a[$i]
        moving      = ($(if ($mv -and $mv.Count -gt $i) { [bool]$mv[$i] } else { ([double]$v[$i] -ge $stop) }))
        heading_deg = [double]$head[$i]
    }
    if ($g.Count -gt $i -and $null -ne $g[$i]) {
        try { $obj.grade = [double]$g[$i] } catch {}
    }
    $samples.Add($obj)
}

# payload for analyze (OBJECT)
$payload = @{
    samples = $samples
    profile = @{ cda=$CdA; crr=$Crr; weight_kg=$WeightKg; calibrated=$false }
}
if ($UseTestWeather) {
    $payload.weather = @{
        wind_ms = $WindMs
        wind_dir_deg = $WindDir
        air_temp_c = $AirTempC
        air_pressure_hpa = $AirPressHpa
    }
}

# call analyze with explicit payload to force a fresh rb-1arg dump
$uri   = "$BASE/sessions/$Sid/analyze?force_recompute=true`&debug=1"
$start = Get-Date
$body  = $payload | ConvertTo-Json -Depth 12 -Compress
$resp  = Invoke-RestMethod -Method POST -Uri $uri -ContentType "application/json" -Body $body

# small wait so the dump lands on disk
Start-Sleep -Milliseconds 300

# pick newest dump strictly after we called analyze
$payloadFile = Get-ChildItem $env:TEMP -Filter "cg_payload_rb-1arg_*.json" |
    Where-Object { $_.LastWriteTime -ge $start } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $payloadFile) {
    Write-Host "[WARN] No fresh rb-1arg dump found after analyze()" -ForegroundColor Yellow
    # fall back to newest, but warn
    $payloadFile = Get-ChildItem $env:TEMP -Filter "cg_payload_rb-1arg_*.json" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $payloadFile) { throw "No rb-1arg dump present in %TEMP%" }
}

Write-Host ("Payload file: {0}" -f $payloadFile.FullName) -ForegroundColor Yellow

$dump = Get-Content $payloadFile.FullName -Raw | ConvertFrom-Json
$wx   = $dump.weather
$smps = @($dump.samples)

Write-Host ("[WX] wind_ms={0} dir={1} T={2}C P={3}hPa" -f `
    ($(if($wx){$wx.wind_ms}else{$null})),
    ($(if($wx){$wx.wind_dir_deg}else{$null})),
    ($(if($wx){$wx.air_temp_c}else{$null})),
    ($(if($wx){$wx.air_pressure_hpa}else{$null}))) -ForegroundColor Cyan
Write-Host ("[DBG] samples={0}" -f $smps.Count) -ForegroundColor DarkGray

$withH = ($smps | Where-Object { $_.PSObject.Properties.Name -contains "heading_deg" -and $_.heading_deg -ne $null }).Count
$vrelP = ($smps | Where-Object { $_.PSObject.Properties.Name -contains "v_rel" }).Count

Write-Host ("[SUM] heading_deg present on {0}/{1}; v_rel present on {2}/{1}" -f $withH, $smps.Count, $vrelP) -ForegroundColor DarkGray

# dump CSV
$outCsv = Join-Path $outDir ("trinn4_weather_heading_{0}.csv" -f $ActivityId)
$smps | Select-Object t, v_ms, heading_deg | Export-Csv -NoTypeInformation -Delimiter ";" -Path $outCsv
Write-Host ("CSV saved: {0}" -f $outCsv) -ForegroundColor Green

# show first 10
$smps | Select-Object -First 10 t, v_ms, heading_deg | Format-Table -AutoSize

Write-Host "== Done ==" -ForegroundColor Cyan


Write-Host "== Done ==" -ForegroundColor Cyan
