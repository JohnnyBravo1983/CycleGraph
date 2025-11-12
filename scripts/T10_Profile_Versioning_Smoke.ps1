$ErrorActionPreference = "Stop"

# Fast base (du sa riktig port er 5175)
$BASE = "http://127.0.0.1:5175"
Write-Host "Using API base: $BASE"

Write-Host "=== T10 Smoke: GET /api/profile/get ==="
$resp1 = Invoke-RestMethod -Method GET -Uri "$BASE/api/profile/get"
$resp1 | ConvertTo-Json -Depth 5

Write-Host "=== T10 Smoke: PUT /api/profile/save (change weight) ==="
$body = @{
  rider_weight_kg  = 83.0
  bike_type        = "road"
  bike_weight_kg   = 8.0
  tire_width_mm    = 28
  tire_quality     = "performance"
  device           = "strava"
  crank_efficiency = 91.0  # ignored (server bestemmer 96/97)
}
$resp2 = Invoke-RestMethod -Method PUT -Uri "$BASE/api/profile/save" -Body ($body | ConvertTo-Json) -ContentType "application/json"
$resp2 | ConvertTo-Json -Depth 5

Write-Host "=== Check audit JSONL ==="
$audit = "logs/profile/profile_versions.jsonl"
if (Test-Path $audit) {
  Get-Content $audit | Select-Object -Last 3
} else {
  Write-Error "Audit file not found: $audit"
  exit 1
}

Write-Host "=== T10 PASS ==="