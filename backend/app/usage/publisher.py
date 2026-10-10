"""Publishes a recorded usage event for aggregation (and, on the Kafka pipeline, lake storage).

Two implementations, selected by settings.usage_pipeline:
- SyncUsagePublisher (default; used in tests/CI so no Kafka broker is required): aggregates
  in-process, in the same request.
- KafkaUsagePublisher (docker-compose demo): publishes the full event to Kafka; the worker
  process consumes it, aggregates (using the exact same function), and writes the raw event
  to the Parquet lake.

Both paths call the same aggregation function (app.usage.aggregation), so billing numbers
are identical regardless of which pipeline is active.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.models import WorkspaceType
from app.usage.aggregation import apply_usage_to_aggregate
from app.usage.lake import write_usage_event_parquet


@dataclass
class UsageEventRecord:
    event_id: str
    customer_id: str
    subscription_id: str
    event_type: str
    quantity: int
    occurred_at: datetime


class UsagePublisher(ABC):
    @abstractmethod
    def publish(
        self, db: Session, tenant_id: str, workspace_type: WorkspaceType, event: UsageEventRecord
    ) -> None: ...


class SyncUsagePublisher(UsagePublisher):
    def publish(self, db: Session, tenant_id: str, workspace_type: WorkspaceType, event: UsageEventRecord) -> None:
        # Write the raw event to the lake in-process too (the Kafka worker does this on the
        # kafka pipeline), so the Usage page — which reads the lake — shows it immediately.
        write_usage_event_parquet(
            tenant_id=tenant_id,
            workspace_type=workspace_type.value,
            event_id=event.event_id,
            customer_id=event.customer_id,
            subscription_id=event.subscription_id,
            event_type=event.event_type,
            quantity=event.quantity,
            occurred_at=event.occurred_at,
        )
        apply_usage_to_aggregate(
            db, tenant_id, workspace_type, event.subscription_id, event.event_type, event.occurred_at.date()
        )


class KafkaUsagePublisher(UsagePublisher):
    def __init__(self) -> None:
        self._producer = None

    def _get_producer(self):
        if self._producer is None:
            from kafka import KafkaProducer

            settings = get_settings()
            self._producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        return self._producer

    def publish(self, db: Session, tenant_id: str, workspace_type: WorkspaceType, event: UsageEventRecord) -> None:
        settings = get_settings()
        producer = self._get_producer()
        message = {
            "tenant_id": tenant_id,
            "workspace_type": workspace_type.value,
            **asdict(event),
            "occurred_at": event.occurred_at.isoformat(),
        }
        producer.send(settings.kafka_usage_topic, value=message)
        producer.flush()


_sync_publisher = SyncUsagePublisher()
_kafka_publisher: KafkaUsagePublisher | None = None


def get_usage_publisher() -> UsagePublisher:
    settings = get_settings()
    if settings.usage_pipeline == "kafka":
        global _kafka_publisher
        if _kafka_publisher is None:
            _kafka_publisher = KafkaUsagePublisher()
        return _kafka_publisher
    return _sync_publisher
