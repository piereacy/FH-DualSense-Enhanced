@echo off
REM Build the standalone single-file EXE of FH-DualSense-Enhanced.
REM Output: FH-DualSense-Enhanced-RN.exe
REM (no install, no traces - MEIPASS auto-cleans on exit)
REM Requires: uv  (https://docs.astral.sh/uv/)

setlocal EnableDelayedExpansion
pushd "%~dp0..\.."

REM MARK: read the internal numeric version from src\pyproject.toml
set "VER="
for /f "tokens=*" %%L in ('findstr /b /c:"version" src\pyproject.toml') do (
    if not defined VER (
        set "LINE=%%L"
        for /f "tokens=2 delims==" %%V in ("!LINE!") do (
            set "RAW=%%V"
            set "RAW=!RAW: =!"
            set "RAW=!RAW:"=!"
            set "VER=!RAW!"
        )
    )
)
if not defined VER (
    echo Could not read version from src\pyproject.toml
    popd
    exit /b 1
)
echo Building FH-DualSense-Enhanced R%VER% and updater helper ...

set "DIST=%~dp0dist"
set "WORK=%~dp0build"
set "HELPER_DIST=%~dp0helper_dist"
set "HELPER_WORK=%~dp0helper_build"

if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%HELPER_WORK%" rmdir /s /q "%HELPER_WORK%"
if exist "%HELPER_DIST%" rmdir /s /q "%HELPER_DIST%"
if exist "%DIST%" (
    rmdir /s /q "%DIST%" 2>nul
    if exist "%DIST%" (
        echo.
        echo ERROR: Could not clean "%DIST%" - a previous FH-DualSense-Enhanced.exe is probably still running.
        echo        Right-click the tray icon and choose Quit, then retry.
        popd
        exit /b 1
    )
)

REM MARK: the helper is copied out of MEIPASS before use, so it can replace the main EXE.
uvx --from "pyinstaller>=6.11.1" pyinstaller "%~dp0update_helper.py" --onefile --windowed --name "FH-DualSense-Update-Helper" --icon "%CD%\src\data\icon.ico" --distpath "%HELPER_DIST%" --workpath "%HELPER_WORK%" --specpath "%HELPER_WORK%" --noconfirm --clean
if errorlevel 1 (
    echo.
    echo Update helper build FAILED.
    popd
    exit /b 1
)

uvx --from "pyinstaller>=6.11.1" --with customtkinter --with textual --with hidapi --with psutil --with dotenv --with pystray --with pillow --with numpy --with sounddevice pyinstaller "%~dp0fhds.spec" --distpath "%DIST%" --workpath "%WORK%" --noconfirm --clean
if errorlevel 1 (
    echo.
    echo Application build FAILED.
    popd
    exit /b 1
)

REM MARK: updater refuses assets without a matching published SHA-256 file.
REM Use Python instead of Get-FileHash because that cmdlet is absent on some
REM windows-latest runner images even though Windows PowerShell is available.
set "APP_EXE=%DIST%\FH-DualSense-Enhanced-R%VER%.exe"
uv run --no-project python "%~dp0write_sha256.py" "%APP_EXE%"
if errorlevel 1 (
    echo.
    echo SHA-256 sidecar generation FAILED.
    popd
    exit /b 1
)
copy /y "docs\THIRD_PARTY_NOTICES.md" "%DIST%\THIRD_PARTY_NOTICES.md" >nul
copy /y "LICENSE" "%DIST%\LICENSE" >nul

echo.
echo Build OK. Executables and SHA-256 files:
dir /b "%DIST%\FH-DualSense-Enhanced-R%VER%.exe*"
popd
endlocal
