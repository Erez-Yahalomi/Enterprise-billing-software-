"""CLI: python demo/import_uci.py [--csv path/to/online_retail_II.csv]

Imports a reproducible subset of the UCI "Online Retail II" public dataset into the DEMO
tenant. The dataset is not bundled with this repo — download it from the UCI Machine
Learning Repository (https://archive.ics.uci.edu/dataset/502/online+retail+ii) and pass
its path, or set UCI_CSV_PATH. Without a file, this is a no-op: the rest of the demo
(synthetic data from seed_data.py) works fully on its own.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.demo.uci_import import import_uci_sample  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to the UCI CSV (defaults to UCI_CSV_PATH or data/uci/online_retail_II.csv)")
    parser.add_argument("--row-limit", type=int, default=100_000)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        count = import_uci_sample(db, csv_path=args.csv, row_limit=args.row_limit)
        print(f"Imported {count} invoices from the UCI dataset." if count else "No UCI CSV found — skipped.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
