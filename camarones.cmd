@echo off
REM Compatibility alias. The public command is camaron.
call "%~dp0camaron.cmd" %*
exit /b %ERRORLEVEL%
