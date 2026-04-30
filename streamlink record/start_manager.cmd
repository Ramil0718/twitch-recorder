@echo off
setlocal EnableExtensions
pushd "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    pause
    exit /b 1
)

echo Starting Twitch recorder manager...
echo Open this URL on the server: http://localhost:8888
echo Open this URL remotely:     http://SERVER_IP:8888
echo.

python manager.py

echo.
echo Manager exited with code %ERRORLEVEL%.
pause
exit /b %ERRORLEVEL%




