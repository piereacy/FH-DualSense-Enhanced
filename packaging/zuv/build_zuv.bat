@echo off
REM Build the FH-DualSense-Enhanced ZUV distribution locally.
REM Optional: set UPDATE_REPO=owner/repository to enable remote update checks.
setlocal
pushd "%~dp0..\.."

set "DIST=%~dp0dist"
set "BUNDLE=%DIST%\FH-DualSense-Enhanced.zuv.py"

if not exist "%DIST%" mkdir "%DIST%"

if defined UPDATE_REPO (
    echo Building update-enabled ZUV for %UPDATE_REPO% ...
    uvx --from "zuv==0.5.6" zuv build src -o "%BUNDLE%" --update-repo "%UPDATE_REPO%"
) else (
    echo Building local ZUV without a remote update source ...
    uvx --from "zuv==0.5.6" zuv build src -o "%BUNDLE%"
)
if errorlevel 1 (
    echo.
    echo ZUV build FAILED.
    popd
    exit /b 1
)

copy /y "win_start.bat" "%DIST%\win_start.bat" >nul
copy /y "linux_start.sh" "%DIST%\linux_start.sh" >nul
copy /y "LICENSE" "%DIST%\LICENSE" >nul
copy /y "docs\THIRD_PARTY_NOTICES.md" "%DIST%\THIRD_PARTY_NOTICES.md" >nul

echo.
echo Build OK. Bundle: %BUNDLE%
popd
endlocal
