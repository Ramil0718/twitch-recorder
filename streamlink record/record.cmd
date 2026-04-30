@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ==================== CONFIG ====================
set "CHANNEL=spicyuuu"
set "OUTPUT_DIR=recordings"
rem Optional proxy, example: http://127.0.0.1:7890
set "PROXY="
rem Quality: best / 1080p60 / 720p60 / 720p / 480p / worst
set "QUALITY=best"
set "CHECK_INTERVAL=60"
rem ================================================

pushd "%~dp0"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

where streamlink >nul 2>nul
if errorlevel 1 (
    echo ERROR: streamlink.exe was not found in PATH.
    echo Try this command:
    echo   python -m streamlink --version
    echo.
    echo If that works, add the Python Scripts folder to PATH,
    echo or run the web manager with: python manager.py
    pause
    exit /b 1
)

echo =========================================
echo   Twitch auto recorder
echo   Channel: %CHANNEL%
echo   Output: %CD%\%OUTPUT_DIR%
echo =========================================

:loop
    for /f "tokens=2 delims==" %%a in ('wmic os get LocalDateTime /value ^| find "="') do set "DT=%%a"
    set "TIMESTAMP=!DT:~0,8!_!DT:~8,6!"
    set "OUTPUT_FILE=%OUTPUT_DIR%\%CHANNEL%_!TIMESTAMP!.ts"

    echo [%DATE% %TIME%] Checking %CHANNEL%...

    set "PROXY_ARGS="
    if not "%PROXY%"=="" set "PROXY_ARGS=--https-proxy %PROXY%"

    streamlink !PROXY_ARGS! --retry-streams 30 --retry-max 0 "https://www.twitch.tv/%CHANNEL%" "%QUALITY%" --output "!OUTPUT_FILE!"
    set "EXIT_CODE=!ERRORLEVEL!"

    if "!EXIT_CODE!"=="0" (
        echo [%DATE% %TIME%] Recording finished: !OUTPUT_FILE!
    ) else (
        echo [%DATE% %TIME%] Stream ended, offline, or failed. Exit code: !EXIT_CODE!
    )
    echo [%DATE% %TIME%] Rechecking in %CHECK_INTERVAL% seconds...

    timeout /t %CHECK_INTERVAL% /nobreak >nul
goto loop

