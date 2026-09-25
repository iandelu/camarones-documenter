@echo off
setlocal enabledelayedexpansion
REM Camaron - one-time global install (Windows).
REM Clones this repo into a fixed central location and puts camaron plus the legacy camarones alias on your PATH,
REM so every cama-docs-* project shares one kit copy instead of a per-project copy going stale.
cd /d "%~dp0"
set "SRC=%~dp0"
set "CENTRAL=%LOCALAPPDATA%\camarones-documenter\kit"
set "BINDIR=%USERPROFILE%\.local\bin"

set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where git >nul 2>nul
if errorlevel 1 (
  echo git is required - install it first: https://git-scm.com/download/win
  pause & exit /b 1
)
where uv >nul 2>nul
if not errorlevel 1 goto haveuv
where winget >nul 2>nul
if errorlevel 1 goto nouv
echo Installing uv with winget - one time...
winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto haveuv
:nouv
echo uv is not installed. Install it, then run install-global.cmd again:
echo    winget install --id=astral-sh.uv -e
pause & exit /b 1
:haveuv

if exist "%CENTRAL%\.git" (
  echo Updating existing central kit at "%CENTRAL%"...
  git -C "%CENTRAL%" pull --ff-only
) else (
  echo Cloning kit to "%CENTRAL%"...
  if not exist "%LOCALAPPDATA%\camarones-documenter" mkdir "%LOCALAPPDATA%\camarones-documenter"
  git clone --quiet "%SRC%." "%CENTRAL%"
)
if errorlevel 1 (
  echo Clone/update failed.
  pause & exit /b 1
)

if not exist "%BINDIR%" mkdir "%BINDIR%"
> "%BINDIR%\camaron.cmd" (
  echo @echo off
  echo set "PYTHONUTF8=1"
  echo set "CAMARONES_GLOBAL=1"
  echo uv run --quiet --script "%CENTRAL%\.camarones\camarones.py" %%*
)
> "%BINDIR%\camarones.cmd" (
  echo @echo off
  echo call "%BINDIR%\camaron.cmd" %%*
  echo exit /b %%ERRORLEVEL%%
)
echo Global launcher written to "%BINDIR%\camaron.cmd"; compatibility alias: camarones.

echo %PATH% | find /i "%BINDIR%" >nul
if not errorlevel 1 goto onpath
for /f "usebackq tokens=2,*" %%A in (`reg query HKCU\Environment /v Path 2^>nul`) do set "USERPATH=%%B"
echo !USERPATH! | find /i "%BINDIR%" >nul
if not errorlevel 1 goto onpath
echo Adding "%BINDIR%" to your user PATH...
setx PATH "%BINDIR%;!USERPATH!" >nul
echo   Done - open a NEW terminal for it to take effect.
:onpath

echo.
echo Camaron installed globally.
echo Open a new terminal and run: camaron new my-project
echo Update every project at once later with: camaron self-update
pause
