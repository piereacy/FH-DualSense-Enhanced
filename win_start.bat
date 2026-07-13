@echo off
REM FH-DualSense-Enhanced Windows launcher.
REM Downloads the ZUV bundle when needed and lets uv provision Python.
setlocal EnableDelayedExpansion

set "DIR=%~dp0"
set "APP=%DIR%app"
set "BUNDLE=%APP%\FH-DualSense-Enhanced.zuv.py"
set "MANUAL=%DIR%FH-DualSense-Enhanced.zuv.py"
set "REPO=piereacy/FH-DualSense-Enhanced"
set "URL=https://github.com/%REPO%/releases/latest/download/FH-DualSense-Enhanced.zuv.py"
set "FLAGS="
set "GAME="

if not exist "%APP%" mkdir "%APP%"
if not exist "%BUNDLE%" (
    if exist "%MANUAL%" (
        echo Using manually downloaded FH-DualSense-Enhanced.zuv.py...
        copy /y "%MANUAL%" "%BUNDLE%" >nul
    )
)
if not exist "%BUNDLE%" (
    echo Downloading FH-DualSense-Enhanced.zuv.py...
    curl.exe -L --fail -o "%BUNDLE%" "%URL%" || (
        echo ERROR: Download failed. Download the ZUV manually from:
        echo https://github.com/%REPO%/releases
        echo Then place it beside win_start.bat and retry.
        pause
        exit /b 1
    )
)

REM Args starting with -- are forwarded to the app. Other args form an optional
REM Steam wrapper command, for example: start "" steam://rungameid/1551360
:argloop
if "%~1"=="" goto ready
set "a=%~1"

if "!a:~0,2!"=="--" goto flag_arg

if defined GAME goto append_game
set "GAME=%1"
goto next_arg
:append_game
set "GAME=!GAME! %1"
goto next_arg
:flag_arg
set "FLAGS=!FLAGS! %1"
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
