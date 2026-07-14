@echo off
setlocal EnableDelayedExpansion
cd /d %~dp0
set FEWS_RELOAD=false
set FEWS_HOST=0.0.0.0

echo ==========================================
echo FEWS LAN Launcher
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
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254*' } ^| Select-Object -First 1 -ExpandProperty IPAddress)"`) do set LOCAL_IP=%%i
if "!LOCAL_IP!"=="" set LOCAL_IP=IP-LAN-TIDAK-TERDETEKSI

echo FEWS berjalan di jaringan lokal.
echo Dari laptop lain buka: http://!LOCAL_IP!:!FEWS_PORT!
echo (Jika belum bisa diakses, izinkan Python/Uvicorn di Windows Firewall)
echo.
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
echo Jika perlu jalankan setup ulang:
echo   .\setup_local.ps1
pause
exit /b 1
