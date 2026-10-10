@echo off
title Corporate Billing Platform
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-demo.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed - see messages above.
  pause
) else (
  timeout /t 5 >nul
)
