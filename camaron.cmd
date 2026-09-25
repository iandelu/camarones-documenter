@echo off
setlocal
chcp 65001 >nul
REM Camaron launcher for Windows. Double-click it, or run: camaron.cmd help
REM It only runs local files. uv (Python tool manager, signed by Astral) is installed with winget if missing.
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto run
where winget >nul 2>nul
if errorlevel 1 goto nouv
echo Installing uv with winget - one time...
winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto run
:nouv
echo.
echo uv is not installed. Install it once, then open camaron.cmd again:
echo    winget install --id=astral-sh.uv -e
echo    or download it from https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1
:run
set "PYTHONUTF8=1"
uv run --quiet --script ".camarones\camarones.py" %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%
