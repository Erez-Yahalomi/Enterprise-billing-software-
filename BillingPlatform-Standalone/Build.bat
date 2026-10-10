@echo off
title Building Corporate Billing Platform
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build.ps1"
if errorlevel 1 (
  echo.
  echo Build failed - see messages above.
) else (
  echo.
  echo Build finished.
)
pause
