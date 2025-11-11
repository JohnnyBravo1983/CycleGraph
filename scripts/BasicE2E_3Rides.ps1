<#
BasicE2E_3Rides.ps1
- Enkel E2E mot analyze-endepunktet for 3 Strava-økter
- Laster .env, refresher Strava-token (om mulig)
- Bygger payload (t, v_ms, altitude, grade), poster til analyze
- Lagrer payload og respons per økt til .\out\
#>

param(
  [string]$Base = "http://127.0.0.1:5175",
  [string]$Sid  = "local-mini",
  [switch]$UseApiPrefix,     # default settes manuelt nedenfor (true)
  [double]$Cda = 0.30,
  [double]$Crr = 0.004,
  [double]$Wkg = 111.0,
  [Int64[]]$Ids  = @(16311219004, 16279854313, 16262232459),
  [switch]$ForceRecompute,
  [int]$DebugLevel = 1
)

$ErrorActionPreference = "Stop"

# --- API-prefiks (/api) default = ON ---
$useApi = $true
if ($PSBoundParameters.ContainsKey('UseApiPrefix')) {
  $useApi = $UseApiPrefix.IsPresent
}
$prefix = if ($useApi) { "/api" } else { "" }

# ForceRecompute som bool-string
$fr = if ($ForceRecompute.IsPresent) { "true" } else { "false" }

$AnalyzeUri = "$Base$prefix/sessions/$Sid/analyze?force_recompute=$fr&debug=$DebugLevel"

# --- .env ---
$envPath = Join-Path (Resolve-Path ".") ".env"
if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    $l = $_.Trim()
    if ($l -and -not $l.StartsWith("#")) {
      $i = $l.IndexOf("=")
      if ($i -gt 0) {
        $k = $l.Substring(0,$i).Trim()
        $v = $l.Substring($i+1).Trim().Trim('"').Trim("'")
        Set-Item -Path env:$k -Value $v -ErrorAction SilentlyContinue
      }
    }
  }
}

# --- Token refresh ---
if ($env:STRAVA_REFRESH_TOKEN) {
  try {
    $tok = Invoke-RestMethod -Method POST -Uri "https://www.strava.com/oauth/token" -Body @{
      client_id     = $env:STRAVA_CLIENT_ID
      client_secret = $env:STRAVA_CLIENT_SECRET
      grant_type    = "refresh_token"
      refresh_token = $env:STRAVA_REFRESH_TOKEN
    }
    $env:STRAVA_ACCESS_TOKEN     = $tok.access_token
    $env:STRAVA_REFRESH_TOKEN    = $tok.refresh_token
    $env:STRAVA_TOKEN_EXPIRES_AT = [string]$tok.expires_at
    "Ny access_token mottatt. Utløper @ $($tok.expires_at) (epoch)."
  } catch {
    "ADVARSEL: Klarte ikke å refreshe token -> $($_.Exception.Message)"
  }
}
if (-not $env:STRAVA_ACCESS_TOKEN) { throw "Mangler STRAVA_ACCESS_TOKEN i miljøet." }

# --- Strava helpers ---
function Get-StravaStreams([Int64]$Id) {
  $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
  $keys = "time,velocity_smooth,altitude,grade_smooth"
  $u = "https://www.strava.com/api/v3/activities/$Id/streams?keys=$keys&key_by_type=true"
  Invoke-RestMethod -Method GET -Headers $h -Uri $u
}
function Get-StravaActivity([Int64]$Id) {
  $h = @{ Authorization = "Bearer $($env:STRAVA_ACCESS_TOKEN)" }
  Invoke-RestMethod -Method GET -Headers $h -Uri "https://www.strava.com/api/v3/activities/$Id"
}

function Build-SessionPayload($S, [double]$CdaLocal, [double]$CrrLocal, [double]$WLocal) {
  $t=@($S.time.data); $v=@($S.velocity_smooth.data); $a=@($S.altitude.data); $g=@($S.grade_smooth.data)
  $tc=$t.Count; $vc=$v.Count; $ac=$a.Count
  $n=[Math]::Min([Math]::Min($tc,$vc),$ac)
  if ($n -le 0) { throw "Streams mangler data (time/velocity/altitude)" }

  $samples = New-Object 'System.Collections.Generic.List[object]'
  for ($i=0; $i -lt $n; $i++) {
    $obj=@{ t=[double]$t[$i]; v_ms=[double]$v[$i]; altitude_m=[double]$a[$i]; moving=$true }
    if ($g.Count -gt $i -and $null -ne $g[$i]) { try { $obj.grade=[double]$g[$i] } catch {} }
    $samples.Add($obj)
  }
  return @{
    samples = $samples
    profile = @{ cda=$CdaLocal; crr=$CrrLocal; weight_kg=$WLocal; calibrated=$false }
  }
}

function Analyze-Session($PayloadJson) {
  Invoke-RestMethod -Method POST -Uri $AnalyzeUri -ContentType "application/json" -Body $PayloadJson
}

# --- Kjør ---
$out  = Join-Path (Resolve-Path ".") "out"; New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($id in $Ids) {
  try {
    $act     = Get-StravaActivity $id
    $streams = Get-StravaStreams  $id
    $payload = Build-SessionPayload $streams $Cda $Crr $Wkg

    $payloadPath = Join-Path $out "session_$id.json"
    ($payload | ConvertTo-Json -Depth 12) | Set-Content $payloadPath -Encoding utf8

    $json = ($payload | ConvertTo-Json -Depth 12 -Compress)
    $res  = Analyze-Session $json
    $m    = $res.metrics

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

    ($res | ConvertTo-Json -Depth 22) | Set-Content (Join-Path $out "result_$id.json") -Encoding utf8
  } catch {
    "FAIL $id -> $($_.Exception.Message)"
  }
}

"=== Kjøring ferdig ==="
"AnalyzeUri = $AnalyzeUri"
