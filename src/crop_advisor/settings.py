"""Small, explicit runtime configuration surface.

Configuration comes from environment variables so that a container image does
not contain deployment secrets or environment-specific paths.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _csv_environment(name: str, default: str) -> tuple[str, ...]:
    values = os.getenv(name, default)
    parsed = tuple(value.strip() for value in values.split(",") if value.strip())
    if not parsed:
        raise ValueError(f"{name} must contain at least one comma-separated value.")
    return parsed


def _positive_integer_environment(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


def _boolean_environment(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


@dataclass(frozen=True)
class Settings:
    environment: str
    allowed_hosts: tuple[str, ...]
    max_request_bytes: int
    model_path: Path
    model_sha256: str | None
    contract_path: Path
    metrics_enabled: bool

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def load_settings() -> Settings:
    """Read settings once at process startup and validate unsafe values early."""

    environment = os.getenv("CROP_ADVISOR_ENV", "development").strip().lower()
    if environment not in {"development", "test", "production"}:
        raise ValueError("CROP_ADVISOR_ENV must be development, test, or production.")
    model_path = Path(
        os.getenv(
            "CROP_ADVISOR_MODEL_PATH",
            str(PROJECT_ROOT / "artifacts" / "maharashtra_crop_suitability_v1" / "model.joblib"),
        )
    )
    contract_path = Path(
        os.getenv(
            "CROP_ADVISOR_CONTRACT_PATH",
            str(PROJECT_ROOT / "data" / "contracts" / "maharashtra_crop_recommendation.v1.json"),
        )
    )
    host_setting = os.getenv("CROP_ADVISOR_ALLOWED_HOSTS")
    if environment == "production" and host_setting is None:
        raise ValueError(
            "CROP_ADVISOR_ALLOWED_HOSTS must be explicitly set in production."
        )
    allowed_hosts = _csv_environment(
        "CROP_ADVISOR_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
    )
    if environment == "production" and "*" in allowed_hosts:
        raise ValueError("Wildcard CROP_ADVISOR_ALLOWED_HOSTS is not allowed in production.")
    model_sha256 = os.getenv("CROP_ADVISOR_MODEL_SHA256", "").strip().lower() or None
    if model_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", model_sha256):
        raise ValueError("CROP_ADVISOR_MODEL_SHA256 must be a lowercase SHA-256 hex digest.")
    if environment == "production" and model_sha256 is None:
        raise ValueError(
            "CROP_ADVISOR_MODEL_SHA256 must be set in production so the model is verified before loading."
        )
    return Settings(
        environment=environment,
        allowed_hosts=allowed_hosts,
        max_request_bytes=_positive_integer_environment("CROP_ADVISOR_MAX_REQUEST_BYTES", 65536),
        model_path=model_path,
        model_sha256=model_sha256,
        contract_path=contract_path,
        # Cloud-hosted deployments should use provider-native telemetry unless
        # /metrics is deliberately placed behind a private scrape network.
        metrics_enabled=_boolean_environment(
            "CROP_ADVISOR_METRICS_ENABLED", default=environment != "production"
        ),
    )
