"""Privacy-preserving logs and low-cardinality Prometheus metrics."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram


LOGGER = logging.getLogger("crop_advisor")


def configure_logging() -> None:
    """Emit structured application events to stdout without changing Uvicorn logs."""

    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


configure_logging()

HTTP_REQUESTS = Counter(
    "crop_advisor_http_requests_total",
    "HTTP responses emitted by Crop Advisor.",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "crop_advisor_http_request_duration_seconds",
    "End-to-end HTTP request duration.",
    ("method", "path"),
)
RECOMMENDATION_REQUESTS = Counter(
    "crop_advisor_recommendation_requests_total",
    "Recommendation requests by outcome, without input values.",
    ("outcome",),
)
MODEL_ARTIFACT_LOADS = Counter(
    "crop_advisor_model_artifact_loads_total",
    "Controlled model-artifact load attempts by outcome.",
    ("outcome",),
)
MODEL_READY = Gauge(
    "crop_advisor_model_ready",
    "Whether a compatible controlled model artifact is loaded (1=yes, 0=no).",
)


def metric_path(path: str) -> str:
    """Avoid creating unbounded metric labels from arbitrary URLs."""

    known_paths = {"/", "/health", "/ready", "/metrics", "/v1/options", "/v1/recommendations"}
    return path if path in known_paths else "other"


def metric_method(method: str) -> str:
    """Keep request-method metric cardinality bounded too."""

    return method if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} else "OTHER"


def request_timer() -> float:
    return perf_counter()


def record_http(method: str, path: str, status_code: int, started_at: float) -> float:
    """Record only operational metadata, never request bodies or farm details."""

    safe_path = metric_path(path)
    safe_method = metric_method(method)
    duration_seconds = perf_counter() - started_at
    HTTP_REQUESTS.labels(method=safe_method, path=safe_path, status=str(status_code)).inc()
    HTTP_REQUEST_DURATION.labels(method=safe_method, path=safe_path).observe(duration_seconds)
    return duration_seconds


def record_recommendation(outcome: str) -> None:
    RECOMMENDATION_REQUESTS.labels(outcome=outcome).inc()


def record_model_load(outcome: str) -> None:
    MODEL_ARTIFACT_LOADS.labels(outcome=outcome).inc()
    MODEL_READY.set(1 if outcome == "success" else 0)


def log_http_event(
    *, method: str, path: str, status_code: int, duration_seconds: float, request_id: str
) -> None:
    """Emit one JSON log line with no input values or personally identifying data."""

    event: dict[str, Any] = {
        "event": "http_request_complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": metric_method(method),
        "path": metric_path(path),
        "status_code": status_code,
        "duration_ms": round(duration_seconds * 1000, 2),
        "request_id": request_id,
    }
    LOGGER.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
