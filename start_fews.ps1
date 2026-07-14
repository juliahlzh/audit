Set-Location $PSScriptRoot
$env:FEWS_RELOAD = "false"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FEWS Local Launcher" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment belum ada. Menjalankan setup awal..." -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File ".\setup_local.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Setup gagal dijalankan." -ForegroundColor Red
        Read-Host "Tekan Enter untuk menutup"
        exit 1
    }
}

& ".\.venv\Scripts\python.exe" ".\run.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "FEWS gagal dijalankan. Baca pesan error di atas." -ForegroundColor Red
    Read-Host "Tekan Enter untuk menutup"
    exit 1
}

Write-Host ""
Read-Host "FEWS berhenti. Tekan Enter untuk menutup"
