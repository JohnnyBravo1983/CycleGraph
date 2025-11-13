# scripts/T11_Run_Matrix.ps1
# Trinn 11 – CI Regression Matrix (kalles både lokalt og i CI)
# Kjører server/analysis/t11_matrix.py og sikrer t11_matrix.csv uten UTF-8 BOM.

$ErrorActionPreference = "Stop"

Write-Host "[T11] Running t11_matrix.py via python"

# Finn python
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

# Kjør t11_matrix.py (den håndterer selv fallback hvis server ikke svarer)
& $python -m server.analysis.t11_matrix
$exit = $LASTEXITCODE

if ($exit -ne 0) {
    Write-Warning "[T11] t11_matrix.py exited with $exit (fallback kan fortsatt ha skrevet artifacts/t11_matrix.csv)"
}

# Sjekk at artifacts og csv finnes
if (-not (Test-Path "artifacts")) {
    throw "[T11] artifacts/ directory missing"
}

$csvPath = "artifacts/t11_matrix.csv"
if (-not (Test-Path $csvPath)) {
    throw "[T11] t11_matrix.csv missing after t11_matrix.py"
}

# --- Strip UTF-8 BOM hvis tilstede (EF BB BF) ---
try {
    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($csvPath)
    if ($bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF) {

        Write-Host "[T11] Stripping UTF-8 BOM from t11_matrix.csv"
        $newBytes = $bytes[3..($bytes.Length - 1)]
        [System.IO.File]::WriteAllBytes($csvPath, $newBytes)
    }
} catch {
    Write-Warning "[T11] Failed to strip BOM (ignored): $($_.Exception.Message)"
}

Write-Host "[T11] Final t11_matrix.csv:"
Get-ChildItem artifacts
