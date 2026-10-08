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

REM The PATH this installer was started with: the launcher folder is checked against it, not against the
REM folders prepended below to find uv.
set "START_PATH=%PATH%"
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
echo !ORIGIN! | "%SystemRoot%\System32\findstr.exe" /c:"://" /c:"@" >nul && set "REPOINT="
if defined CAMARONES_KIT_URL set "REPOINT=1"
if defined REPOINT git -C "%CENTRAL%" remote set-url origin "%KIT_URL%"
git -C "%CENTRAL%" pull --ff-only --quiet 2>nul
if not errorlevel 1 goto cloned
REM Upstream history was rewritten (rebased, amended): move onto it like `camaron self-update` does, as long as
REM nothing is uncommitted and every local commit already exists upstream by content.
git -C "%CENTRAL%" fetch --quiet
if errorlevel 1 (
  echo Could not reach the kit upstream from "%CENTRAL%".
  pause & exit /b 1
)
for /f "usebackq delims=" %%S in (`git -C "%CENTRAL%" status --porcelain --untracked-files^=no`) do (
  echo The kit clone "%CENTRAL%" has uncommitted changes - commit or discard them, then retry.
  pause & exit /b 1
)
for /f "usebackq delims=" %%C in (`git -C "%CENTRAL%" cherry @{u} HEAD ^| "%SystemRoot%\System32\findstr.exe" /b /l "+"`) do (
  echo The kit clone "%CENTRAL%" has local commits that are not upstream - push or drop them, then retry.
  pause & exit /b 1
)
git -C "%CENTRAL%" reset --hard --quiet @{u}
if errorlevel 1 (
  echo Could not move "%CENTRAL%" onto the kit upstream.
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

REM Windows' own find.exe: under Git Bash a bare `find` is GNU find, which made this check always fail.
echo ;%START_PATH%; | "%SystemRoot%\System32\find.exe" /i "%BINDIR%" >nul
if not errorlevel 1 goto onpath
REM Never setx: it truncates PATH at 1024 characters. PowerShell edits the registry value in place (keeping
REM %VARIABLES%) only if the folder is not there yet, then tells Windows the environment changed.
echo Adding "%BINDIR%" to your user PATH...
set "CAM_BINDIR=%BINDIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b = $env:CAM_BINDIR.TrimEnd('\'); $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment'); $parts = @(([string]$k.GetValue('Path', '', 'DoNotExpandEnvironmentNames')) -split ';' | Where-Object { $_ }); if (@($parts | ForEach-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') }) -notcontains $b) { $k.SetValue('Path', ((@($b) + $parts) -join ';'), 'ExpandString'); [Environment]::SetEnvironmentVariable('CAMARON_PATH_REFRESH', '1', 'User'); [Environment]::SetEnvironmentVariable('CAMARON_PATH_REFRESH', $null, 'User') }"
if errorlevel 1 (
  echo   Could not change your PATH - add "%BINDIR%" to it by hand.
) else (
  echo   Done - open a NEW terminal for it to take effect.
)
:onpath

echo.
echo Camaron installed globally.
echo Open a new terminal and run: camaron new my-project
echo Update every project at once later with: camaron self-update
pause
