CORPORATE BILLING PLATFORM - STANDALONE (NO DOCKER)
===================================================

This folder is a separate package. It reads the project's backend/ and frontend/ folders but
never changes them, so the Docker version keeps working exactly as before.

RUN IT (double-click)
  dist\BillingPlatform\BillingPlatform.exe      (or Start-BillingPlatform.bat)

  - A small window opens, then your browser opens the app at http://127.0.0.1:8765
  - Demo data is already included, so it starts in a few seconds.
  - Keep the window open while you use the app. Close it to stop.
  - Needs nothing installed: no Docker, no Python, no database server.
  - To share it, zip the whole dist\BillingPlatform folder (the exe needs the files beside it).

WHERE YOUR DATA LIVES
  %LOCALAPPDATA%\BillingPlatform\
    billing.db   the SQLite database (delete it to reset to fresh demo data)
    lake\        usage analytics files
    .env         settings (AI provider / Gemini key); edit, save, restart the app

DIFFERENCES FROM THE DOCKER VERSION
  - SQLite instead of Postgres; usage events are processed in-process instead of via Kafka;
    policy checks run embedded instead of via an OPA server (the project's built-in
    "embedded" modes, the same ones its tests use).
  - AI Assistant uses the built-in rule-based assistant by default. For the Gemini model, put
    your key in the .env file above. The local Ollama model is not included.
    On the very first launch the app opens a small window with the link and steps to get a
    free Gemini key and a box to paste it in; it saves the key to the .env file for you
    (Skip uses the built-in assistant).

REBUILD THE EXE (only if you change the project code)
  Double-click Build.bat. It needs Python 3 (with tkinter, included in the python.org installer) and an internet connection, and puts everything it
  downloads (portable Node.js, Python packages) inside this folder under tools\.
  Output: dist\BillingPlatform\BillingPlatform.exe
