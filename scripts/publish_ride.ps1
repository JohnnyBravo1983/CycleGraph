param(
  [string]$BaseUrl = "http://127.0.0.1:5179",
  [string]$SessionId = "ride3",
  [switch]$AnalyzeFirst
)

$ErrorActionPreference = 'Stop'

function Call($method, $uri) {
  try {
    if ($method -eq "GET")  { return Invoke-RestMethod -Method Get  -Uri $uri -ErrorAction Stop }
    if ($method -eq "POST") { return Invoke-RestMethod -Method Post -Uri $uri -ErrorAction Stop }
  } catch {
    $resp = $_.Exception.Response
    if ($resp) {
      $sr = New-Object System.IO.StreamReader($resp.GetResponseStream())
      $body = $sr.ReadToEnd()
      Write-Host "HTTP status: " ([int]$resp.StatusCode)
      Write-Host "Body: $body"
    } else { Write-Host $_ }
    throw
  }
}

Write-Host "▶ Health..."
$h = Call "GET" "$BaseUrl/api/health"
$h | ConvertTo-Json -Depth 5

Write-Host "`n▶ Token present?"
$t = Call "GET" "$BaseUrl/api/debug/token_present"
$t | ConvertTo-Json -Depth 5

if ($AnalyzeFirst) {
  Write-Host "`n▶ Analyze $SessionId ..."
  $an = Call "POST" "$BaseUrl/api/sessions/$SessionId/analyze"
  if ($an) { $an | ConvertTo-Json -Depth 8 | Write-Host } else { Write-Host "(no body)" }
}

Write-Host "`n▶ Publish $SessionId ..."
$pub = Call "POST" "$BaseUrl/api/sessions/$SessionId/publish"
if ($pub) { $pub | ConvertTo-Json -Depth 8 | Write-Host } else { Write-Host "(no body)" }

# Dump status fra session-fil
$sessionPath = ".\data\sessions\$SessionId.json"
if (Test-Path $sessionPath) {
  Write-Host "`n▶ Session status ($sessionPath)"
  Get-Content $sessionPath -Raw | ConvertFrom-Json |
    Select-Object session_id, precision_watt, precision_watt_ci, CdA, crr_used, publish_toggle, strava_activity_id, publish_state, publish_error |
    Format-List
} else {
  Write-Host "`n(i) Fant ikke $sessionPath"
}
