@echo off
REM Build three standalone single-file EXEs of FH-DualSense-Enhanced.
REM Output: ...-RN-Miku-Console.exe, ...-Miku-Stage.exe, ...-Miku-Studio.exe
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
echo Building FH-DualSense-Enhanced R%VER% updater helper and three GUI variants ...

set "DIST=%~dp0dist"
set "WORK=%~dp0build"
set "HELPER_DIST=%~dp0helper_dist"
set "HELPER_WORK=%~dp0helper_build"
set "GENERATED=%~dp0generated"

if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%HELPER_WORK%" rmdir /s /q "%HELPER_WORK%"
if exist "%HELPER_DIST%" rmdir /s /q "%HELPER_DIST%"
if exist "%GENERATED%" rmdir /s /q "%GENERATED%"
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

for %%V in (console stage studio) do (
    set "FHDS_BUILD_VARIANT=%%V"
    echo.
    echo Building %%V variant ...
    uvx --from "pyinstaller>=6.11.1" --with customtkinter --with textual --with hidapi --with psutil --with dotenv --with pystray --with pillow --with numpy --with sounddevice pyinstaller "%~dp0fhds.spec" --distpath "%DIST%" --workpath "%WORK%\%%V" --noconfirm --clean
    if errorlevel 1 (
        echo.
        echo %%V variant build FAILED.
        popd
        exit /b 1
    )
)
set "FHDS_BUILD_VARIANT="

REM MARK: updater refuses assets without a matching published SHA-256 file.
for %%F in ("%DIST%\*.exe") do (
    powershell -NoProfile -Command "$p='%%~fF'; $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant(); [IO.File]::WriteAllText($p+'.sha256', $h+'  '+[IO.Path]::GetFileName($p), [Text.Encoding]::ASCII)"
)
copy /y "docs\THIRD_PARTY_NOTICES.md" "%DIST%\THIRD_PARTY_NOTICES.md" >nul
copy /y "LICENSE" "%DIST%\LICENSE" >nul

echo.
echo Build OK. Executables and SHA-256 files:
dir /b "%DIST%\FH-DualSense-Enhanced-R%VER%-Miku-*.exe*"
popd
endlocal
