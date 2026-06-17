@echo off
setlocal
cd /d %~dp0
set FEWS_RELOAD=false

echo ==========================================
echo FEWS Local Launcher
echo ==========================================
echo.

if not exist .venv\Scripts\python.exe (
    echo Virtual environment belum ada. Menjalankan setup awal...
    powershell -ExecutionPolicy Bypass -File "%~dp0setup_local.ps1"
    if errorlevel 1 goto :error
)

".\.venv\Scripts\python.exe" run.py
if errorlevel 1 goto :error

echo.
echo FEWS berhenti normal.
pause
exit /b 0

:error
echo.
echo FEWS gagal dijalankan.
echo Pastikan internet/internal repo untuk install package tersedia lalu jalankan lagi.
echo Jika perlu, buka PowerShell di folder ini dan jalankan:
echo   .\setup_local.ps1
echo   python run.py
pause
exit /b 1
