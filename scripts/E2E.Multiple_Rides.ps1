# =====================================================================
# CycleGraph Precision Watt testkj??ring ??? Rust-first (flere ??kter)
# =====================================================================
# - Kun ASCII-tegn (ingen em-dash, ingen greske symboler)
# - Heading beregnes fra lat/lon, sender weather_hint (midpoint + hour)
# - STRAVA_ACCESS_TOKEN m?? v??re satt i milj??et (ev. .env load)
# =====================================================================

$ErrorActionPreference = "Stop"

# --- 1) Basis ---
$Base = "http://127.0.0.1:5175/api"   # inkluderer /api-prefiks
$ForceRecompute = $true
$DebugLevel     = 1   # 0/1

# V??r: la server hente selv (default). Sett $UseTestWeather=$true for ?? injisere test-v??r.
$UseTestWeather = $false
$TestWeather = @{
  wind_ms          = 3.0
  wind_dir_deg     = 270.0
  air_temp_c       = 12.0
  air_pressure_hpa = 1013.0
}

# --- 2) Aktiviteter som skal analyseres ---
$Ids = @(
  16311219004,  # baseline test
  16279854313,
  16262232459,
  16127771071,
  16333270450,  # ny ??kt
  16342459294,  # ny ??kt
  16381383185,
  16396031026,
  16405483541
)

# --- 2.1 Hjelpere (grader<->radianer + bearing) ---
function To-Rad([double]$deg) { [Math]::PI * $deg / 180.0 }
function Bearing-Deg([double]$lat1, [double]$lon1, [double]$lat2, [double]$lon2) {
    $r1  = To-Rad $lat1
    $r2  = To-Rad $lat2
    $dLo = To-Rad ($lon2 - $lon1)
    $y   = [Math]::Sin($dLo) * [Math]::Cos($r2)
    $x   = [Math]::Cos($r1) * [Math]::Sin($r2) - [Math]::Sin($r1) * [Math]::Cos($r2) * [Math]::Cos($dLo)
    $deg = [Math]::Atan2($y, $x) * 180.0 / [Math]::PI
    if ($deg -lt 0) { $deg += 360.0 }
    return $deg
}

# --- 3) Strava helpers ---
function Get-StravaStreams([long]$Id) {
    $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
    $keys = "time,velocity_smooth,altitude,grade_smooth,latlng,distance,moving"
    $u = "https://www.strava.com/api/v3/activities/$Id/streams?keys=$keys&key_by_type=true"
    Invoke-RestMethod -Method GET -Headers $h -Uri $u
}
function Get-StravaActivity([long]$Id) {
    $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
    Invoke-RestMethod -Method GET -Headers $h -Uri "https://www.strava.com/api/v3/activities/$Id"
}

# --- 4) Profil (HARDKODET for test) ---
$Cda = 0.30
$Crr = 0.004
$Wkg = 111.0

# --- 4.1 Formatering/verifikasjon av v??r fra respons ---
function Format-WeatherUsed($metrics) {
    try {
        $meta = $metrics.weather_meta
        $wx   = $metrics.weather_used
        $fp   = $metrics.weather_fp

        if ($null -ne $meta -and $null -ne $wx) {
            $lat = if ($meta.lat_used -ne $null) { [Math]::Round([double]$meta.lat_used,5) } else { "<na>" }
            $lon = if ($meta.lon_used -ne $null) { [Math]::Round([double]$meta.lon_used,5) } else { "<na>" }
            $hr  = if ($meta.ts_hour -ne $null)  { [string]$meta.ts_hour } else { "<na>" }
            $fp8 = if ($fp) { $fp.Substring(0, [Math]::Min(8,$fp.Length)) } else { "--------" }
            $t   = $wx.air_temp_c
            $p   = $wx.air_pressure_hpa
            $wms = $wx.wind_ms
            $wdd = $wx.wind_dir_deg
            return "[WX*] used hour=$hr lat=$lat lon=$lon fp=$fp8 -> T=$t C  P=$p hPa  wind_ms=$wms  dir=$wdd deg"
        }
        return $null
    } catch {
        return $null
    }
}

# --- 5) Bygg payload m/ heading_deg + LAT/LON + ABSOLUTT TID (+ valgfri weather) ---
function Build-SessionPayload(
    $S,
    [double]$CdaLocal,
    [double]$CrrLocal,
    [double]$WLocal,
    [bool]$IncludeWeather=$false,
    $WeatherObj=$null,
    [string]$StartISO=$null
) {
    $t  = @($S.time.data)
    $v  = @($S.velocity_smooth.data)
    $a  = @($S.altitude.data)
    $g  = @($S.grade_smooth.data)
    $ll = @($S.latlng.data)

    $tc=$t.Count; $vc=$v.Count; $ac=$a.Count
    $lc=($ll | ForEach-Object { $_ }) | Measure-Object | Select-Object -ExpandProperty Count
    if (-not $lc) { $lc = 0 }

    $n_baseline = [Math]::Min([Math]::Min($tc,$vc), $ac)
    $n = if ($lc -gt 0) { [Math]::Min($n_baseline, $lc) } else { $n_baseline }
    if ($n -le 0) { throw "Streams mangler data (time/velocity/altitude)" }

    # heading_deg + lat/lon per sample
    $headings = $null
    if ($lc -gt 1) {
        $headings = New-Object 'System.Collections.Generic.List[double]'
        for ($i=0; $i -lt $n; $i++) {
            if ($i -lt ($n-1) -and $ll[$i] -ne $null -and $ll[$i+1] -ne $null) {
                $lat1 = [double]$ll[$i][0];   $lon1 = [double]$ll[$i][1]
                $lat2 = [double]$ll[$i+1][0]; $lon2 = [double]$ll[$i+1][1]
                $hdg = Bearing-Deg $lat1 $lon1 $lat2 $lon2
            } elseif ($i -gt 0) {
                $hdg = $headings[$i-1]
            } else {
                $hdg = 0.0
            }
            $headings.Add([double]$hdg)
        }
        if ($headings.Count -ge 2) { $headings[0] = $headings[1] }
        Write-Host ("[GPS] latlng OK - heading_deg beregnet for {0} punkter" -f $headings.Count) -ForegroundColor Green
    } else {
        Write-Host "[GPS] latlng mangler/skjult - kj??rer uten heading_deg (vind retningskomp ??? 0)" -ForegroundColor Yellow
    }

    # Absolutt start (UNIX s) fra activity.start_date (UTC)
    $t0 = $null
    if ($StartISO) {
        try {
            $t0 = [DateTimeOffset]::Parse($StartISO).ToUnixTimeSeconds()
        } catch { $t0 = $null }
    }

    # samples (med lat/lon + ev. t_abs)
    $samples = New-Object 'System.Collections.Generic.List[object]'
    $latSum = 0.0; $lonSum = 0.0; $llCount = 0
    $speedStop = 0.5

    for ($i=0; $i -lt $n; $i++) {
        $obj = @{
            t          = [double]$t[$i]
            v_ms       = [double]$v[$i]
            altitude_m = [double]$a[$i]
            moving     = ([double]$v[$i] -ge $speedStop)
        }

        if ($g.Count -gt $i -and $null -ne $g[$i]) {
            try { $obj.grade=[double]$g[$i] } catch {}
        }
        if ($headings -and $headings.Count -gt $i) {
            $obj.heading_deg = [double]$headings[$i]
        }
        if ($lc -gt $i -and $null -ne $ll[$i]) {
            $lat = [double]$ll[$i][0]; $lon = [double]$ll[$i][1]
            $obj.lat_deg = $lat
            $obj.lon_deg = $lon
            $latSum += $lat; $lonSum += $lon; $llCount++
        }
        if ($t0 -ne $null) {
            $obj.t_abs = [double]($t0 + [double]$t[$i])  # absolutte sekunder
        }

        $samples.Add($obj)
    }

    # Beregn "senter" og n??rmeste time (til hint)
    $centerLat = $null; $centerLon = $null; $hintHour = $null
    if ($llCount -gt 0) {
        $centerLat = $latSum / $llCount
        $centerLon = $lonSum / $llCount
    }
    if ($t0 -ne $null -and $n -gt 0) {
        # velg midt-sample som representativ tid
        $midIdx = [int][Math]::Floor(($n-1)/2)
        $tAbsMid = [double]($t0 + [double]$t[$midIdx])
        # rund til n??rmeste hele time (sekunder)
        $hour = [int][Math]::Round($tAbsMid / 3600.0) * 3600
        $hintHour = $hour
    }

    $payload = @{
        samples = $samples
        profile = @{ cda=$CdaLocal; crr=$CrrLocal; weight_kg=$WLocal; calibrated=$false }
    }

    # Send et hint til serveren
    $weather_hint = @{}
    if ($centerLat -ne $null -and $centerLon -ne $null) {
        $weather_hint.lat_deg = [double]$centerLat
        $weather_hint.lon_deg = [double]$centerLon
    }
    if ($hintHour -ne $null) {
        $weather_hint.ts_hour = [int]$hintHour
    }
    if ($weather_hint.Count -gt 0) {
        $payload.weather_hint = $weather_hint
    }

    if ($IncludeWeather -and $null -ne $WeatherObj) {
        # Kun for testing; i normal drift la denne v??re av
        $payload.weather = $WeatherObj
    }

    return $payload
}

# --- 6) Analyze API call ---
function Analyze-Session($Payload) {
    $json = ($Payload | ConvertTo-Json -Depth 14 -Compress)
    $qs = "?force_recompute=$($ForceRecompute.ToString().ToLower())&debug=$DebugLevel"
    Invoke-RestMethod -Method POST `
        -Uri "$Base/sessions/local-mini/analyze$qs" `
        -ContentType "application/json" -Body $json
}

# --- 7) Preflight: verifiser at vi faktisk f??r latlng fra Strava ---
Write-Host "=== Preflight: sjekker latlng p?? f??rste ID ==="
try {
    $pf = Get-StravaStreams $Ids[0]
    $hasLL = ($pf.latlng -and $pf.latlng.data -and $pf.latlng.data.Count -gt 1)
    if ($hasLL) {
        Write-Host ("OK {0}: latlng OK (count={1})" -f $Ids[0], $pf.latlng.data.Count) -ForegroundColor Green
    } else {
        Write-Host ("WARN {0}: latlng mangler - sjekk token-scopes (activity:read_all) og aktivitetens kart-privacy" -f $Ids[0]) -ForegroundColor Yellow
    }
} catch {
    Write-Host ("Preflight feilet: {0}" -f $_.Exception.Message) -ForegroundColor Red
}

# --- 8) Kj??r for hver aktivitet ---
$out = "_debug"; if (-not (Test-Path $out)) { New-Item -ItemType Directory -Path $out | Out-Null }
$summary = New-Object 'System.Collections.Generic.List[object]'

foreach ($id in $Ids) {
    try {
        $act     = Get-StravaActivity $id
        $streams = Get-StravaStreams  $id

        # Alltid server-v??r for aktuell ??kt, men vi sender lat/lon + t_abs (+ hint)
        if ($UseTestWeather) {
            $payload = Build-SessionPayload $streams $Cda $Crr $Wkg $true  $TestWeather $act.start_date
        } else {
            $payload = Build-SessionPayload $streams $Cda $Crr $Wkg $false $null        $act.start_date
        }

        # lagre payload for revisjon
        ($payload | ConvertTo-Json -Depth 14) | Set-Content (Join-Path $out "session_$id.json") -Encoding utf8

        if ($payload.ContainsKey("weather")) {
            $w=$payload.weather
            Write-Host ("[WX] payload weather (TEST) -> T={0} C  P={1} hPa  wind_ms={2}  dir={3} deg" -f $w.air_temp_c,$w.air_pressure_hpa,$w.wind_ms,$w.wind_dir_deg) -ForegroundColor Cyan
        } else {
            if ($payload.weather_hint) {
                $wh = $payload.weather_hint
                $lat = $wh.lat_deg; $lon = $wh.lon_deg; $hr = $wh.ts_hour
                Write-Host ("[WX~hint] hour={0} lat={1} lon={2}" -f $hr, ([Math]::Round($lat,5)), ([Math]::Round($lon,5))) -ForegroundColor DarkCyan
            } else {
                Write-Host "[WX] payload weather -> <none> (server henter selv)" -ForegroundColor DarkCyan
            }
        }

        $res = Analyze-Session $payload

        # lagre respons for revisjon
        ($res | ConvertTo-Json -Depth 22) | Set-Content (Join-Path $out "result_$id.json") -Encoding utf8

        $m   = $res.metrics

        # Vis hva serveren faktisk brukte av v??r (hvis exposed)
        $wxLine = Format-WeatherUsed $m
        if ($wxLine) {
            Write-Host $wxLine -ForegroundColor DarkYellow
        } else {
            Write-Host "[WX?] server eksponerte ikke weather_meta/weather_used - kan ikke verifisere time/posisjon" -ForegroundColor Yellow
        }

        $P=[double]$m.precision_watt
        $D=[double]$m.drag_watt
        $R=[double]$m.rolling_watt
        $avg=[double]$act.average_watts
        $dev=$act.device_watts

        $diff=$null; $pct=$null
        if ($avg -gt 0) { $diff=$P-$avg; $pct=100.0*$diff/$avg }

        $dragPct=($(if($P){100*$D/$P}else{0}))
        $rollPct=($(if($P){100*$R/$P}else{0}))
        $ratioTxt = if ($pct -ne $null) {
            ("Delta={0:+0.0} W ({1:+0.0} %) vs Strava{2}" -f $diff,$pct,($(if($dev){" (device)"}else{" (est)"})))
        } else { "Strava avg_watts n/a" }

        "{0} | src={1} uf={2} wa={3} | P={4:N1} D={5:N1} ({6,5:N1} %) R={7:N1} ({8,5:N1} %) | {9} | Profile: CdA={10}, Crr={11}, W={12}" -f `
            $id,$res.source,$res.debug.used_fallback,$res.weather_applied,`
            $P,$D,$dragPct,$R,$rollPct,$ratioTxt,$Cda,$Crr,$Wkg

        # --- Oppsummeringsrad ---
        $wxm = $m.weather_meta
        $wxu = $m.weather_used
        $obj = [PSCustomObject]@{
            id              = $id
            source          = $res.source
            used_fallback   = $res.debug.used_fallback
            weather_applied = $res.weather_applied
            precision_watt  = [double]$P
            drag_pct        = [double]$dragPct
            rolling_pct     = [double]$rollPct
            strava_avg_w    = $(if($avg -gt 0){[double]$avg}else{$null})
            delta_w         = $(if($diff -ne $null){[double]$diff}else{$null})
            delta_pct       = $(if($pct  -ne $null){[double]$pct }else{$null})
            wx_hour         = $(if($wxm){$wxm.ts_hour}else{$payload.weather_hint.ts_hour})
            wx_lat          = $(if($wxm){[double]$wxm.lat_used}else{$payload.weather_hint.lat_deg})
            wx_lon          = $(if($wxm){[double]$wxm.lon_used}else{$payload.weather_hint.lon_deg})
            wx_temp_c       = $(if($wxu){[double]$wxu.air_temp_c}else{$null})
            wx_press_hpa    = $(if($wxu){[double]$wxu.air_pressure_hpa}else{$null})
            wx_wind_ms      = $(if($wxu){[double]$wxu.wind_ms}else{$null})
            wx_wind_dir     = $(if($wxu){[double]$wxu.wind_dir_deg}else{$null})
            wx_fp           = $m.weather_fp
        }
        $summary.Add($obj) | Out-Null

    } catch {
        "FAIL $id -> $($_.Exception.Message)"
    }
}

# --- 9) Eksporter oppsummering ---
$csvPath = Join-Path $out "weather_summary.csv"
$summary | Export-Csv -Path $csvPath -NoTypeInformation
Write-Host ("[OK] Skrev oppsummering: {0}" -f $csvPath) -ForegroundColor Green

"=== Kj??ring ferdig ==="

