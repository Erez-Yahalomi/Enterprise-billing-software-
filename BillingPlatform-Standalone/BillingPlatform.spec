# PyInstaller spec: builds dist\BillingPlatform\BillingPlatform.exe
# Reads ..\backend (unmodified) plus the outputs of Build.ps1 (build\frontend, build\seed_data).
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

here = Path(SPECPATH)
backend = here.parent / "backend"

datas = [
    (str(here / "build" / "frontend"), "frontend_dist"),
    (str(here / "build" / "seed_data"), "seed_data"),
]
binaries = []
hiddenimports = collect_submodules("app") + collect_submodules("uvicorn") + collect_submodules("sqlalchemy.dialects.sqlite")

# Packages with data files / native pieces that static analysis misses.
for pkg in ("duckdb", "pyarrow", "google.generativeai", "email_validator", "tzdata"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    [str(here / "launcher.py")],
    pathex=[str(backend)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "kafka", "psycopg", "alembic"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BillingPlatform",
    console=True,  # small status window; closing it stops the app
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="BillingPlatform")
