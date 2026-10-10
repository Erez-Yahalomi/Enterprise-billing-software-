"""Lightweight big-data analytics: DuckDB queries the raw Parquet usage lake directly,
no Spark/Trino cluster required for this scale of demo data (see spec section 8/25)."""

from datetime import date
from pathlib import Path

import duckdb

from app.analytics.schemas import UsageByDayItem
from app.core.config import get_settings


def query_usage_by_day(
    tenant_id: str, subscription_id: str, period_start: date, period_end: date
) -> list[UsageByDayItem]:
    settings = get_settings()
    lake_usage_dir = Path(settings.lake_path) / "usage"
    if not lake_usage_dir.exists() or not any(lake_usage_dir.rglob("*.parquet")):
        return []

    glob_pattern = str(lake_usage_dir / "**" / "*.parquet")
    # Hive-partition columns can be inferred as VARCHAR when only one partition value is
    # present (e.g. a single day in the lake so far), so cast explicitly before make_date.
    query = """
        SELECT
            make_date(CAST(year AS BIGINT), CAST(month AS BIGINT), CAST(day AS BIGINT)) AS day,
            event_type, SUM(quantity) AS total_quantity
        FROM read_parquet(?, hive_partitioning=true)
        WHERE tenant_id = ? AND subscription_id = ?
            AND make_date(CAST(year AS BIGINT), CAST(month AS BIGINT), CAST(day AS BIGINT)) BETWEEN ? AND ?
        GROUP BY year, month, day, event_type
        ORDER BY day
    """
    # duckdb.sql() shares one global connection that isn't safe across FastAPI's worker
    # threads (concurrent requests raise "unsuccessful or closed pending query result"),
    # so each call gets its own short-lived in-memory connection.
    con = duckdb.connect()
    try:
        rows = con.execute(query, [glob_pattern, tenant_id, subscription_id, period_start, period_end]).fetchall()
    finally:
        con.close()
    return [UsageByDayItem(day=row[0], event_type=row[1], total_quantity=int(row[2])) for row in rows]
