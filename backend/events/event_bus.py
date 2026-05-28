from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Optional

import redis

from backend.config.settings import settings
from backend.events.domain_events import DomainEvent
from backend.observability.metrics import record_counter

logger = logging.getLogger(__name__)


class EventBus:
    """
    Thin Redis-backed event bus.

    Phase-1 implementation uses Redis Streams for durability and fan-out.
    """

    STREAM_KEY = "veda:domain_events"

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = redis.Redis.from_url(redis_url or settings.REDIS_URL)

    def publish(self, event: DomainEvent) -> bool:
        try:
            payload = asdict(event)
            # Redis Streams require flat field/value pairs (bytes/str).
            # Store the entire payload as JSON under a single field.
            self._redis.xadd(self.STREAM_KEY, {"event": json.dumps(payload)}, maxlen=100000, approximate=True)
            record_counter("event_bus.publish.success", event_type=event.event_type)
            return True
        except Exception:
            logger.exception("Failed to publish domain event")
            record_counter("event_bus.publish.error", event_type=getattr(event, "event_type", "unknown"))
            return False


event_bus = EventBus()

