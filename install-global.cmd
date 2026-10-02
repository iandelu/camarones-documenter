@echo off
setlocal enabledelayedexpansion
REM Camaron - one-time global install (Windows).
REM Clones the kit into a fixed central location and puts camaron plus the legacy camarones alias on your PATH,
REM so every cama-docs-* project shares one kit copy instead of a per-project copy going stale.
REM Works from a checkout or downloaded on its own (see README for the one-line PowerShell install).
REM CAMARONES_KIT_URL overrides where the kit comes from (a fork, or a local checkout while developing the kit).
cd /d "%~dp0"
set "KIT_URL=https://github.com/iandelu/camarones-documenter.git"
if defined CAMARONES_KIT_URL set "KIT_URL=%CAMARONES_KIT_URL%"
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

if not exist "%CENTRAL%\.git" goto clone
echo Updating existing central kit at "%CENTRAL%"...
set "ORIGIN="
for /f "usebackq delims=" %%U in (`git -C "%CENTRAL%" remote get-url origin 2^>nul`) do set "ORIGIN=%%U"
REM Older installs followed a local checkout; a remote URL (a fork) is kept unless CAMARONES_KIT_URL says otherwise.
set "REPOINT=1"
echo !ORIGIN! | findstr /c:"://" /c:"@" >nul && set "REPOINT="
if defined CAMARONES_KIT_URL set "REPOINT=1"
if defined REPOINT git -C "%CENTRAL%" remote set-url origin "%KIT_URL%"
git -C "%CENTRAL%" pull --ff-only --quiet
if errorlevel 1 (
  echo Could not fast-forward "%CENTRAL%" - run: camaron self-update
  pause & exit /b 1
)
goto cloned
:clone
echo Cloning kit to "%CENTRAL%"...
if not exist "%LOCALAPPDATA%\camarones-documenter" mkdir "%LOCALAPPDATA%\camarones-documenter"
git clone --quiet "%KIT_URL%" "%CENTRAL%"
if errorlevel 1 (
  echo Clone failed.
  pause & exit /b 1
)
:cloned

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
