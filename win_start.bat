@echo off
REM FH DualSense - Windows launcher (zuv).
REM Bundle self-updates from GitHub Releases on each run; ZUV_NO_UPDATE=1 disables.
setlocal
set "DIR=%~dp0"
set "BUNDLE=%DIR%fhds.zuv.py"
set "GAME_CMD=%*"

if not exist "%BUNDLE%" (
    echo Could not find %BUNDLE%.
    echo Download fhds.zuv.py from https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python/releases/latest
    pause
    exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv...
    powershell -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul || (echo uv not on PATH - restart terminal. & pause & exit /b 1)
)

REM Optional Steam wrapper: pass `start "" steam://rungameid/1551360` (or any cmd)
REM as launcher args. The game starts; fhds runs until the game exits.
if defined GAME_CMD start "" %GAME_CMD%

uv run "%BUNDLE%"
if not defined GAME_CMD pause >nul
endlocal
