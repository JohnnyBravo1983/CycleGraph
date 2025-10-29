Param(
  [string]$Base = "http://127.0.0.1:5180",
  [string]$ProfileDevice = "strava",
  [double]$ProfileCdA = 0.28,
  [double]$ProfileCrr = 0.004,
  [double]$ProfileWeightKg = 78.0
)

Write-Host "🚴‍♂️  CycleGraph 5-ride pipeline starter på $Base"

# === Sjekk API (ikke obligatorisk, men gir bekreftelse) ===
try {
  $h = Invoke-RestMethod "$Base/api/health"
  if($h.status -eq "ok"){ Write-Host "✅ API health OK" }
} catch { Write-Warning "⚠️  Health-sjekk feilet, fortsetter uansett..." }

# === Finn GPX-filer ===
$gpxFiles = Get-ChildItem -Path "data\gpx\*.gpx" -ErrorAction SilentlyContinue
if(-not $gpxFiles -or $gpxFiles.Count -lt 1){ throw "Ingen GPX i data\gpx" }

$ACTS = @()
for($i=0; $i -lt $gpxFiles.Count; $i++){
  $id  = [IO.Path]::GetFileNameWithoutExtension($gpxFiles[$i].Name)
  $sid = "ride{0}" -f ($i+1)
  $ACTS += @{ id=$id; sid=$sid; gpx=$gpxFiles[$i].FullName }
}

Write-Host ("📦 Fant {0} GPX-filer: {1}" -f $gpxFiles.Count, ([string]::Join(", ", ($ACTS | ForEach-Object { $_.sid })) ))

# === Opprett sessions, last opp GPX, hent & apply vær ===
foreach($a in $ACTS){
  Write-Host "▶️  Session $($a.sid)"
  Invoke-RestMethod -Method Post -Uri "$Base/api/sessions/$($a.sid)/create" | Out-Null
  Invoke-RestMethod -Method Post -Uri "$Base/api/sessions/$($a.sid)/upload/gpx" -InFile $a.gpx -ContentType "application/octet-stream" | Out-Null
  Invoke-RestMethod -Method Post -Uri "$Base/api/sessions/$($a.sid)/weather/fetch?source=open-meteo" | Out-Null
  Invoke-RestMethod -Method Post -Uri "$Base/api/sessions/$($a.sid)/weather/apply" | Out-Null
}

# === Analyze med profil ===
$profile = @{
  CdA       = $ProfileCdA
  Crr       = $ProfileCrr
  weight_kg = $ProfileWeightKg
  device    = $ProfileDevice
}

$rows = @()
foreach($a in $ACTS){
  Write-Host "🔍 Analyze $($a.sid)..."
  $body = @{ profile = $profile } | ConvertTo-Json -Depth 6
  $r = Invoke-RestMethod -Method Post -Uri "$Base/api/sessions/$($a.sid)/analyze?force_recompute=true&cache_bust=$(New-Guid)" `
       -Body $body -ContentType "application/json"
  $r | ConvertTo-Json -Depth 12 | Out-File -FilePath ("logs\session_{0}_analyze.json" -f $a.sid) -Encoding UTF8
  $rows += [pscustomobject]@{
    session        = $a.sid
    activity_id    = $a.id
    precision_watt = [double]$r.metrics.precision_watt
    drag_watt      = [double]$r.metrics.drag_watt
    rolling_watt   = [double]$r.metrics.rolling_watt
    v_rel          = [double]$r.metrics.v_rel
    rho            = [double]$r.metrics.rho
  }
}

# === Lag CSV og skriv tabell ===
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$csvPath = "logs\precision_watt_results_5.csv"
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath
$rows | Format-Table -AutoSize
Write-Host "✅ Resultater lagret: $csvPath"
