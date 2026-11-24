@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -File "%~dp0scripts\setup-windows.ps1" %*
set "setup_exit=%ERRORLEVEL%"
if "%setup_exit%"=="3010" echo Reinicia Windows y vuelve a ejecutar install.cmd.
if not "%setup_exit%"=="0" (
  echo Si una politica de empresa bloquea PowerShell o la instalacion, consulta con IT.
  pause
)
exit /b %setup_exit%
