"""One-click launcher for the Corporate Billing Platform (no Docker, no Postgres, no Kafka).

Runs the existing FastAPI backend (../backend) on an embedded SQLite database and serves the
built React frontend from the same local port, then opens the browser. Nothing in the original
project is modified: this file only imports from it.

Works both from source (`python launcher.py`) and frozen by PyInstaller (BillingPlatform.exe).
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PACKAGE_DIR = Path(__file__).resolve().parent

PORT_RANGE = range(8765, 8785)
HOST = "127.0.0.1"
ENV_TEMPLATE = """\
# Corporate Billing Platform - local settings. Edit, save, then restart the app.
#
# AI Assistant: leave AI_PROVIDER=mock for the built-in rule-based assistant, or set
# AI_PROVIDER=gemini and paste a free key from https://aistudio.google.com/apikey
AI_PROVIDER=mock
GEMINI_API_KEY=
"""


def locate_backend() -> Path:
    for candidate in (BUNDLE_ROOT / "backend", PACKAGE_DIR.parent / "backend"):
        if (candidate / "app" / "main.py").exists():
            return candidate
    raise SystemExit("Could not find the backend code (expected ../backend/app/main.py).")


def locate_frontend() -> Path:
    for candidate in (BUNDLE_ROOT / "frontend_dist", PACKAGE_DIR / "build" / "frontend"):
        if (candidate / "index.html").exists():
            return candidate
    raise SystemExit("Frontend build not found. Run Build.bat first (see README.txt).")


def data_dir() -> Path:
    override = os.environ.get("BILLING_DATA_DIR")
    base = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BillingPlatform"
    base.mkdir(parents=True, exist_ok=True)
    return base


def configure_environment(data: Path) -> None:
    """Must run before the backend is imported: app.core.db reads settings at import time."""
    # cwd = data dir so the backend's `.env` lookup finds the user-editable settings file there
    # instead of picking up some unrelated .env from wherever the exe was launched.
    os.chdir(data)
    env_file = data / ".env"
    if not env_file.exists():
        env_file.write_text(ENV_TEMPLATE, encoding="utf-8")

    os.environ["DATABASE_URL"] = f"sqlite:///{(data / 'billing.db').as_posix()}"
    os.environ["LAKE_PATH"] = str(data / "lake")
    os.environ["USAGE_PIPELINE"] = "sync"  # no Kafka
    os.environ["OPA_MODE"] = "embedded"  # no OPA server
    os.environ.setdefault("ENVIRONMENT", "production")


GEMINI_URL = "https://aistudio.google.com/apikey"
GEMINI_STEPS = (
    "The AI Assistant works best with Google's Gemini model, which has a free tier.\n"
    "To get your free API key:\n\n"
    "  1. Open the link below and sign in with any Google account.\n"
    "  2. Click \"Create API key\" (choose any project if asked).\n"
    "  3. Copy the key (it starts with \"AIza\") and paste it in the box below.\n\n"
    "You can skip this; the app then uses a simpler built-in assistant. You can add the key\n"
    "later by editing the .env file in the data folder."
)


def _read_env_values(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def save_gemini_key(env_file: Path, key: str) -> None:
    """Put the key in .env and switch the AI provider to Gemini (falls back to rules if it fails)."""
    wanted = {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": key}
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        name = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and name in wanted:
            lines[i] = f"{name}={wanted[name]}"
            seen.add(name)
    lines += [f"{k}={v}" for k, v in wanted.items() if k not in seen]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ask_key_window() -> str | None:
    """Small input window. Returns the pasted key, '' if skipped, None if no GUI is available."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        return None
    try:
        root = tk.Tk()
    except Exception:
        return None
    root.title("Corporate Billing Platform - Gemini API key")
    root.resizable(False, False)
    result = {"key": ""}

    tk.Label(root, text="Set up the AI Assistant (free)", font=("Segoe UI", 13, "bold")).pack(
        anchor="w", padx=16, pady=(14, 4))
    tk.Label(root, text=GEMINI_STEPS, justify="left", font=("Segoe UI", 10)).pack(anchor="w", padx=16)
    link = tk.Label(root, text=GEMINI_URL, fg="#0b5fff", cursor="hand2", font=("Segoe UI", 10, "underline"))
    link.pack(anchor="w", padx=16, pady=(6, 10))
    link.bind("<Button-1>", lambda _e: webbrowser.open(GEMINI_URL))

    tk.Label(root, text="Paste your Gemini API key here:", font=("Segoe UI", 10)).pack(anchor="w", padx=16)
    entry = tk.Entry(root, width=58, font=("Consolas", 10))
    entry.pack(padx=16, pady=(2, 12))
    entry.focus_set()

    def save():
        key = entry.get().strip().strip('"').strip("'")
        if len(key) < 20 or " " in key:
            messagebox.showwarning("That does not look like a key",
                                   "A Gemini API key is a single long string of letters and numbers "
                                   "(usually starting with AIza). Please copy it again, or click Skip.",
                                   parent=root)
            return
        result["key"] = key
        root.destroy()

    buttons = tk.Frame(root)
    buttons.pack(anchor="e", padx=16, pady=(0, 14))
    tk.Button(buttons, text="Skip for now", width=14, command=root.destroy).pack(side="left", padx=6)
    tk.Button(buttons, text="Save key", width=14, command=save, default="active").pack(side="left")
    root.bind("<Return>", lambda _e: save())

    root.update_idletasks()  # centre on screen
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
    root.attributes("-topmost", True)
    root.mainloop()
    return result["key"]


def first_run_gemini_setup(data: Path) -> None:
    """First launch only: ask for a free Gemini key, explain how to get one, store it in .env."""
    env_file = data / ".env"
    marker = data / ".gemini-setup-done"
    if marker.exists() or _read_env_values(env_file).get("GEMINI_API_KEY"):
        return
    key = _ask_key_window()
    if key is None:  # no GUI available: ask in the console instead
        print("\n" + GEMINI_STEPS + f"\n\n  Link: {GEMINI_URL}\n", flush=True)
        try:
            key = input("Paste your Gemini API key (or press Enter to skip): ").strip().strip('"')
        except EOFError:
            key = ""
    if key:
        save_gemini_key(env_file, key)
        print("Gemini key saved.", flush=True)
    else:
        print("Skipped. Using the built-in assistant (edit .env later to add a key).", flush=True)
    marker.write_text("asked\n", encoding="utf-8")


def install_bundled_seed(data: Path) -> None:
    """First run: start from the demo database shipped inside the app instead of generating it."""
    seed = BUNDLE_ROOT / "seed_data"
    if (data / "billing.db").exists() or not (seed / "billing.db").exists():
        return
    print("First run: installing demo data...", flush=True)
    shutil.copy2(seed / "billing.db", data / "billing.db")
    if (seed / "lake").exists():
        shutil.copytree(seed / "lake", data / "lake", dirs_exist_ok=True)


def browser_url(base: str) -> str:
    """The address to open in the browser. The changing ?v= makes it a URL the browser has never cached,
    so a freshly launched app always shows the current UI even if an older page was cached earlier.
    (Same origin, so saved settings such as the chosen workspace are unaffected.)"""
    return f"{base}/?v={int(time.time())}"


def pick_port() -> int:
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    raise SystemExit(f"No free port in {PORT_RANGE.start}-{PORT_RANGE.stop - 1}.")


def already_running() -> int | None:
    """If another copy is already serving, return its port so we just open the browser."""
    import httpx

    for port in PORT_RANGE:
        try:
            r = httpx.get(f"http://{HOST}:{port}/api/health", timeout=0.4)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return port
        except Exception:
            continue
    return None


def build_app(frontend: Path):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from sqlalchemy import event

    from app.core.db import Base, engine
    from app.main import app as backend_app

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        # WAL + NORMAL is crash-safe and far faster than the default for write-heavy seeding.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.close()

    Base.metadata.create_all(engine)

    root = FastAPI(title="Corporate Billing Platform (standalone)", docs_url=None, redoc_url=None, openapi_url=None)
    # The frontend calls /api/<route>; the mount strips the prefix, matching the Vite dev proxy.
    root.mount("/api", backend_app)

    index = frontend / "index.html"
    frontend_resolved = frontend.resolve()

    # Without this the browser may reuse a cached copy of the page for hours after a rebuild and keep
    # showing the old UI. "no-cache" means: always ask the server again (it re-sends the files; that's
    # fine on localhost).
    no_cache = {"Cache-Control": "no-cache"}

    @root.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path:
            candidate = (frontend / path).resolve()
            if frontend_resolved in candidate.parents and candidate.is_file():
                return FileResponse(candidate, headers=no_cache)
            if "." in Path(path).name:  # a missing asset should 404, not return the HTML shell
                raise HTTPException(status_code=404)
        return FileResponse(index, headers=no_cache)

    return root


def seed_demo_data(port: int) -> None:
    """First run only: same call the Docker start script makes."""
    import httpx

    base = f"http://{HOST}:{port}/api"
    headers = {"X-Tenant-Id": "DEMO", "X-Workspace-Type": "demo"}
    try:
        existing = httpx.get(f"{base}/customers", headers=headers, timeout=60).json()
        if existing:
            return
        print("First run: generating demo data (this takes a moment)...", flush=True)
        httpx.post(
            f"{base}/demo/generate",
            headers=headers,
            json={"size": "medium", "include_uci": False},
            timeout=900,
        ).raise_for_status()
        print("Demo data ready.", flush=True)
    except Exception as exc:  # not fatal: the Demo Data page in the UI can do the same thing
        print(f"Could not generate demo data automatically ({exc}). Use the Demo Data page in the app.", flush=True)


def wait_until_up(port: int, timeout: float = 60) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://{HOST}:{port}/api/health", timeout=1).status_code == 200:
                return True
        except Exception:
            time.sleep(0.25)
    return False


def main(make_seed: bool = False) -> None:
    print("Corporate Billing Platform", flush=True)

    if not make_seed:
        running = already_running()
        if running:
            print(f"Already running on port {running} - opening it in your browser.", flush=True)
            webbrowser.open(browser_url(f"http://{HOST}:{running}"))
            return

    data = data_dir()
    configure_environment(data)
    if not make_seed:
        install_bundled_seed(data)
        first_run_gemini_setup(data)  # must run before the backend reads its settings

    if not FROZEN:  # the packaged exe already contains the backend modules
        backend = locate_backend()
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
    frontend = locate_frontend()

    import uvicorn

    print("Starting...", flush=True)
    app = build_app(frontend)
    port = pick_port()
    url = f"http://{HOST}:{port}"

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning", log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not wait_until_up(port):
        raise SystemExit("The server did not start in time.")
    seed_demo_data(port)

    if make_seed:  # build-time: leave a ready demo database behind and exit
        server.should_exit = True
        thread.join(15)
        from app.core.db import engine

        engine.dispose()  # checkpoints the WAL so billing.db is self-contained
        print(f"Seed database written to {data}", flush=True)
        return

    print(f"\nRunning at {url}", flush=True)
    print(f"Your data is saved in: {data}", flush=True)
    print("Keep this window open while you use the app. Close it (or press Ctrl+C) to stop.\n", flush=True)
    webbrowser.open(browser_url(url))

    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(5)


if __name__ == "__main__":
    try:
        main(make_seed="--make-seed" in sys.argv)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            print(f"\nERROR: {exc.code}", flush=True)
            if FROZEN:
                input("Press Enter to close...")
            raise
