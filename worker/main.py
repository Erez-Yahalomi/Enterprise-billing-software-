"""Kafka consumer worker: aggregates usage into Postgres and writes raw events to the
Parquet lake. Runs the exact same aggregation function as the backend's synchronous
fallback path (app.usage.aggregation) so numbers never diverge between pipelines.
"""

import json
import logging
import sys
import time
from datetime import date, datetime

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.models import WorkspaceType
from app.usage.aggregation import apply_usage_to_aggregate
from app.usage.lake import write_usage_event_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
log = logging.getLogger("worker")


def process_message(db: Session, message: dict) -> None:
    tenant_id = message["tenant_id"]
    workspace_type = WorkspaceType(message["workspace_type"])
    occurred_at = datetime.fromisoformat(message["occurred_at"])

    write_usage_event_parquet(
        tenant_id=tenant_id,
        workspace_type=workspace_type.value,
        event_id=message["event_id"],
        customer_id=message["customer_id"],
        subscription_id=message["subscription_id"],
        event_type=message["event_type"],
        quantity=message["quantity"],
        occurred_at=occurred_at,
    )

    period_date: date = occurred_at.date()
    apply_usage_to_aggregate(
        db, tenant_id, workspace_type, message["subscription_id"], message["event_type"], period_date
    )
    log.info("processed usage event %s (subscription=%s type=%s)", message["event_id"], message["subscription_id"], message["event_type"])


def connect_consumer(settings) -> KafkaConsumer:
    last_error: Exception | None = None
    for attempt in range(30):
        try:
            return KafkaConsumer(
                settings.kafka_usage_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="billing-worker",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
        except NoBrokersAvailable as exc:
            last_error = exc
            log.info("Kafka not ready yet (attempt %s/30), retrying...", attempt + 1)
            time.sleep(2)
    raise RuntimeError("Could not connect to Kafka") from last_error


def main() -> None:
    settings = get_settings()
    log.info("Starting usage worker, topic=%s brokers=%s", settings.kafka_usage_topic, settings.kafka_bootstrap_servers)
    consumer = connect_consumer(settings)

    for record in consumer:
        db = SessionLocal()
        try:
            process_message(db, record.value)
        except Exception:
            log.exception("Failed to process usage event: %s", record.value)
        finally:
            db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
