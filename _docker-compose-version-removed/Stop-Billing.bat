@echo off
title Stop Corporate Billing Platform
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-demo.ps1"
echo.
pause
