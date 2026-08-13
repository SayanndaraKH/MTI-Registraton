@echo off
title MTI Registration App
cd /d "%~dp0"

echo ===================================================
echo   MTI Registration Application
echo   Local PC:        http://127.0.0.1:8000
echo   Admin Dashboard: http://127.0.0.1:8000/admin
echo   LAN IP:          http://192.168.100.14:8000
echo   Radmin VPN IP:   http://26.169.173.173:8000
echo ===================================================
echo.

IF EXIST .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    python run.py
) ELSE (
    python run.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application stopped with an error.
    pause
)