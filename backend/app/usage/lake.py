"""Writes raw usage events into the local Parquet lake, partitioned the same way the
spec's Cloudflare R2 layout would be: usage/year=YYYY/month=MM/day=DD/part-*.parquet.

Local disk stands in for R2 in this demo; swapping in R2 later just means pointing this
at an S3-compatible client (boto3) instead of the local filesystem — the partition
layout and file format (Parquet) stay identical.
"""

from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import get_settings


def write_usage_event_parquet(
    *,
    tenant_id: str,
    workspace_type: str,
    event_id: str,
    customer_id: str,
    subscription_id: str,
    event_type: str,
    quantity: int,
    occurred_at: datetime,
) -> Path:
    settings = get_settings()
    partition_dir = (
        Path(settings.lake_path)
        / "usage"
        / f"year={occurred_at.year:04d}"
        / f"month={occurred_at.month:02d}"
        / f"day={occurred_at.day:02d}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)

    table = pa.table(
        {
            "tenant_id": [tenant_id],
            "workspace_type": [workspace_type],
            "event_id": [event_id],
            "customer_id": [customer_id],
            "subscription_id": [subscription_id],
            "event_type": [event_type],
            "quantity": [quantity],
            "occurred_at": [occurred_at],
        }
    )
    # Filename is keyed on event_id (not random) so a Kafka redelivery of the same event
    # overwrites its own file instead of creating a duplicate row in the lake.
    file_path = partition_dir / f"part-{event_id}.parquet"
    pq.write_table(table, file_path)
    return file_path


def write_usage_events_batch(*, file_key: str, events: list[dict]) -> Path:
    """Writes many events that share one occurred_at day into a single Parquet file.

    Used by bulk loaders (demo seed) where one file per event would be impractical. Each
    event dict has the same keys as write_usage_event_parquet's keyword arguments. The
    file is named part-{file_key}.parquet so re-running a loader overwrites its own output.
    """
    occurred_at = events[0]["occurred_at"]
    partition_dir = (
        Path(get_settings().lake_path)
        / "usage"
        / f"year={occurred_at.year:04d}"
        / f"month={occurred_at.month:02d}"
        / f"day={occurred_at.day:02d}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.table({key: [e[key] for e in events] for key in events[0]})
    file_path = partition_dir / f"part-{file_key}.parquet"
    pq.write_table(table, file_path)
    return file_path


def delete_lake_files(prefix: str) -> None:
    """Removes every usage Parquet file whose name starts with part-{prefix} (demo reset)."""
    usage_dir = Path(get_settings().lake_path) / "usage"
    if usage_dir.exists():
        for path in usage_dir.rglob(f"part-{prefix}*.parquet"):
            path.unlink()
