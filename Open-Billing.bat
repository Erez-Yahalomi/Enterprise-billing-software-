@echo off
title Open Corporate Billing Platform (Kubernetes)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open-kubernetes-demo.ps1"
if errorlevel 1 (
  echo.
  echo Could not open the platform - see messages above.
  pause
) else (
  timeout /t 5 >nul
)
