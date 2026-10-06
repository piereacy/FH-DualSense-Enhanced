@echo off
REM FH-DualSense-Enhanced Windows launcher.
REM Downloads the ZUV bundle when needed and lets uv provision Python.
setlocal DisableDelayedExpansion

set "DIR=%~dp0"
set "APP=%DIR%app"
set "BUNDLE=%APP%\FH-DualSense-Enhanced.zuv.py"
set "PART=%BUNDLE%.part"
set "MANUAL=%DIR%FH-DualSense-Enhanced.zuv.py"
set "REPO=piereacy/FH-DualSense-Enhanced"
set "URL=https://github.com/%REPO%/releases/latest/download/FH-DualSense-Enhanced.zuv.py"
set "FLAGS="
set "GAME="
set "APP_MODE="
set "GAME_MODE="

if not exist "%APP%" mkdir "%APP%"
if not exist "%BUNDLE%" (
    if exist "%MANUAL%" (
        echo Using manually downloaded FH-DualSense-Enhanced.zuv.py...
        copy /y "%MANUAL%" "%BUNDLE%" >nul
    )
)
if not exist "%BUNDLE%" (
    echo Downloading FH-DualSense-Enhanced.zuv.py...
    curl.exe -L --fail -o "%PART%" "%URL%" || (
        del /q "%PART%" >nul 2>nul
        echo ERROR: Download failed. Download the ZUV manually from:
        echo https://github.com/%REPO%/releases
        echo Then place it beside win_start.bat and retry.
        pause
        exit /b 1
    )
    move /y "%PART%" "%BUNDLE%" >nul
    if errorlevel 1 exit /b 1
)

REM App arguments keep their values and original quoting, for example:
REM   win_start.bat --host 127.0.0.1 --port 5301
REM A standalone -- starts an optional Steam wrapper command:
REM   win_start.bat --headless -- "C:\Program Files\Steam\steam.exe" -applaunch 1551360
REM A command as the first argument remains a legacy wrapper-only invocation.
REM To mix app options and a wrapper, put app options first and use --.
REM Keep delayed expansion disabled so literal ! in paths/values survives.
:argloop
if [%1]==[] goto ready
if defined GAME_MODE goto game_arg
if "%~1"=="--" goto game_mode
if defined APP_MODE goto flag_arg
set "FIRST=%~1"
if "%FIRST:~0,1%"=="-" goto flag_arg
set "GAME_MODE=1"
:game_arg
set GAME=%GAME% %1
goto next_arg
:game_mode
set "GAME_MODE=1"
goto next_arg
:flag_arg
set "APP_MODE=1"
set FLAGS=%FLAGS% %1
:next_arg
shift
goto argloop

:ready
where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv from https://astral.sh/uv/install.ps1 ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
    where uv >nul 2>nul || (
        echo ERROR: uv was installed but is not available on PATH.
        echo Restart Windows or install uv manually, then retry.
        pause
        exit /b 1
    )
)

if defined GAME start "" %GAME%

REM Do not let a host Python installation leak into the managed ZUV runtime.
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "UV_PYTHON_PREFERENCE=only-managed"

uv run "%BUNDLE%" %FLAGS%
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
