Write-Host "Starting CycleGraph backend with auto-reload..."
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn app:app --reload --port 5175