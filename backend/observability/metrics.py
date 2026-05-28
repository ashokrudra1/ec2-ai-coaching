from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)
_METRICS_LOCK = Lock()
_COUNTERS: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], int] = defaultdict(int)
_GAUGES: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
_LATENCIES: Dict[str, float] = {}


def _labels_key(labels: dict) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items()))


def record_counter(name: str, value: int = 1, **labels) -> None:
    """
    Phase-1 metrics shim.

    In production, swap implementation to Prometheus/StatsD/OpenTelemetry exporter.
    """
    try:
        with _METRICS_LOCK:
            _COUNTERS[(name, _labels_key(labels))] += int(value)
        logger.debug({"metric": name, "type": "counter", "value": value, "labels": labels})
    except Exception:
        pass


def record_gauge(name: str, value: float, **labels) -> None:
    try:
        with _METRICS_LOCK:
            _GAUGES[(name, _labels_key(labels))] = float(value)
        logger.debug({"metric": name, "type": "gauge", "value": value, "labels": labels})
    except Exception:
        pass


def record_latency_ms(name: str, latency_ms: float, **labels) -> None:
    try:
        rounded = round(float(latency_ms), 2)
        with _METRICS_LOCK:
            _LATENCIES[name] = rounded
        logger.debug({"metric": name, "type": "latency_ms", "value": rounded, "labels": labels})
    except Exception:
        pass


@contextmanager
def measure_latency(name: str, **labels):
    start = time.time()
    try:
        yield
    finally:
        record_latency_ms(name, (time.time() - start) * 1000.0, **labels)


def snapshot_metrics() -> dict:
    with _METRICS_LOCK:
        counters = [
            {"name": name, "labels": dict(labels), "value": value}
            for (name, labels), value in _COUNTERS.items()
        ]
        gauges = [
            {"name": name, "labels": dict(labels), "value": value}
            for (name, labels), value in _GAUGES.items()
        ]
        latencies = dict(_LATENCIES)
    return {"counters": counters, "gauges": gauges, "latencies_ms": latencies}

