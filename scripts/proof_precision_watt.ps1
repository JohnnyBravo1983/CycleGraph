param(
  [int]$Port = 5177,
  [string]$Sid = "16184045158",
  [string]$SamplesPath = ""
)

if (-not $SamplesPath -or -not (Test-Path $SamplesPath)) {
  $candidate = Join-Path "logs" ("inline_samples_{0}.json" -f $Sid)
  if (Test-Path $candidate) { $SamplesPath = $candidate }
}

if (-not (Test-Path $SamplesPath)) {
  throw "Fant ikke samples-fil. Oppgi -SamplesPath, eller lagre som logs\inline_samples_${Sid}.json"
}

Write-Host "--- Proof: precision_watt vs CdA (med samples) ---"
$samples = Get-Content -Raw -Path $SamplesPath | ConvertFrom-Json

function Run-Test([double]$cda) {
  $u = "http://127.0.0.1:$Port/api/sessions/$Sid/analyze?force_recompute=true"
  $body = @{
    profile = @{
      CdA      = $cda
      Crr      = 0.004
      weightKg = 78
      device   = "strava"
    }
    samples = $samples
  } | ConvertTo-Json -Depth 6

  $resp = Invoke-WebRequest -Uri $u -Method POST -Body $body -ContentType "application/json"
  $json = $resp.Content | ConvertFrom-Json
  [PSCustomObject]@{
    CdA            = $cda
    Source         = $json.source
    Precision_Watt = [double]$json.metrics.precision_watt
  }
}

$res = @()
$res += Run-Test -cda 0.25
$res += Run-Test -cda 0.28
$res += Run-Test -cda 0.32
$res | Format-Table -AutoSize
