"""CLI: python demo/seed_data.py [--size small|medium|large] [--include-uci]

Thin wrapper around backend/app/demo/service.py so the demo generator can be run
standalone (matches the repo layout in the spec). The Demo Data admin page in the UI
calls the same generator via POST /demo/generate.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.demo.service import generate_demo  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="medium")
    parser.add_argument("--include-uci", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = generate_demo(db, args.size, args.include_uci)
        print(f"Generated demo data: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
