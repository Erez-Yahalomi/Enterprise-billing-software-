@echo off
rem Convenience launcher: runs the built app. (Double-clicking dist\BillingPlatform\BillingPlatform.exe does the same.)
if not exist "%~dp0dist\BillingPlatform\BillingPlatform.exe" (
  echo BillingPlatform.exe has not been built yet. Run Build.bat first.
  pause
  exit /b 1
)
start "" "%~dp0dist\BillingPlatform\BillingPlatform.exe"
