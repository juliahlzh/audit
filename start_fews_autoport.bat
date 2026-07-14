@echo off
setlocal EnableDelayedExpansion
cd /d %~dp0
set FEWS_RELOAD=false
set FEWS_HOST=127.0.0.1

echo ==========================================
echo FEWS Auto Port Launcher
echo ==========================================
echo.

if not exist .venv\Scripts\python.exe (
    echo Virtual environment belum ada. Menjalankan setup awal...
    powershell -ExecutionPolicy Bypass -File "%~dp0setup_local.ps1"
    if errorlevel 1 goto :error
)

set PORT=8000
set MAX_PORT=8100
:find_port
netstat -ano -p TCP | findstr /R /C:":!PORT! .*LISTENING" >nul
if not errorlevel 1 (
    set /a PORT+=1
    if !PORT! GTR !MAX_PORT! goto :port_error
    goto :find_port
)

set FEWS_PORT=!PORT!
echo Port dipilih: !FEWS_PORT!
echo Menjalankan FEWS di http://%FEWS_HOST%:!FEWS_PORT!
".\.venv\Scripts\python.exe" run.py
if errorlevel 1 goto :error

echo.
echo FEWS berhenti normal.
pause
exit /b 0

:port_error
echo.
echo Tidak ada port kosong pada rentang 8000-8100.
echo Tutup aplikasi yang memakai port tersebut lalu jalankan lagi.
pause
exit /b 1

:error
echo.
echo FEWS gagal dijalankan.
echo Pastikan internet/internal repo untuk install package tersedia lalu jalankan lagi.
echo Jika perlu, buka PowerShell di folder ini dan jalankan:
echo   .\setup_local.ps1
echo   python run.py
pause
exit /b 1
