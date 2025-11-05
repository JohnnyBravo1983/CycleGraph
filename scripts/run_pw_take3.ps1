# Kjør: .\scripts\pw_take3_min.ps1
Set-Location "C:\Users\easy2\OneDrive\Skrivebord\Archieve\Karriere\CycleGraph"
.\.venv\Scripts\Activate.ps1

if (-not (Test-Path .\_debug)) { New-Item _debug -ItemType Directory | Out-Null }

maturin develop --release -m .\core\Cargo.toml
python -c "import cyclegraph_core as cg; print('OK', hasattr(cg,'compute_power_with_wind_json'))"

$env:CG_DEBUG="1"
python -X dev -u .\cli\analyze.py --help

python -X dev -u .\cli\analyze.py --ids "16311219004,16279854313,16262232459,16127771071,15908409437" --save-report .\_debug\pw_take3.json 2>&1 | Tee-Object -FilePath .\_debug\pw_take3.log
Write-Host "DONE → _debug\pw_take3.json + _debug\pw_take3.log"
