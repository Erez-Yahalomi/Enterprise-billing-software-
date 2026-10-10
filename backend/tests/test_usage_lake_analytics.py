from datetime import date, datetime, timezone

from app.analytics.service import query_usage_by_day
from app.core.config import get_settings
from app.usage.lake import write_usage_event_parquet


def test_write_and_query_usage_lake(tmp_path, monkeypatch):
    monkeypatch.setenv("LAKE_PATH", str(tmp_path))
    get_settings.cache_clear()
    try:
        write_usage_event_parquet(
            tenant_id="DEMO",
            workspace_type="demo",
            event_id="evt-1",
            customer_id="cus_1",
            subscription_id="sub_1",
            event_type="api_request",
            quantity=100,
            occurred_at=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
        )
        # Redelivery of the same event_id overwrites its own file rather than duplicating.
        write_usage_event_parquet(
            tenant_id="DEMO",
            workspace_type="demo",
            event_id="evt-1",
            customer_id="cus_1",
            subscription_id="sub_1",
            event_type="api_request",
            quantity=100,
            occurred_at=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
        )

        results = query_usage_by_day("DEMO", "sub_1", date(2026, 9, 1), date(2026, 9, 30))
        assert len(results) == 1
        assert results[0].event_type == "api_request"
        assert results[0].total_quantity == 100
        assert results[0].day == date(2026, 9, 15)
    finally:
        get_settings.cache_clear()
