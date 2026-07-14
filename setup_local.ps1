python -m venv .venv

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Gagal membuat virtual environment." -ForegroundColor Red
    exit 1
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "Gagal meng-upgrade pip di virtual environment." -ForegroundColor Red
    exit 1
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Gagal meng-install dependency FEWS." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Jika Tesseract tidak ada di PATH, set environment variable berikut:" -ForegroundColor Yellow
Write-Host '$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"'
Write-Host ""
Write-Host "Jalankan aplikasi dengan:" -ForegroundColor Green
Write-Host ".\.venv\Scripts\python.exe .\run.py"
