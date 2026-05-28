from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


def record_counter(name: str, value: int = 1, **labels) -> None:
    """
    Phase-1 metrics shim.

    In production, swap implementation to Prometheus/StatsD/OpenTelemetry exporter.
    """
    try:
        logger.debug({"metric": name, "type": "counter", "value": value, "labels": labels})
    except Exception:
        pass


def record_gauge(name: str, value: float, **labels) -> None:
    try:
        logger.debug({"metric": name, "type": "gauge", "value": value, "labels": labels})
    except Exception:
        pass


def record_latency_ms(name: str, latency_ms: float, **labels) -> None:
    try:
        logger.debug({"metric": name, "type": "latency_ms", "value": round(float(latency_ms), 2), "labels": labels})
    except Exception:
        pass


@contextmanager
def measure_latency(name: str, **labels):
    start = time.time()
    try:
        yield
    finally:
        record_latency_ms(name, (time.time() - start) * 1000.0, **labels)

