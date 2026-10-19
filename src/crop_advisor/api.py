"""Small typed HTTP boundary for the prototype recommendation service.

Authentication, farm storage, and external access are intentionally deferred.
This endpoint handles anonymous, validated requests only and avoids logging the
full request body.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .contracts import load_contract
from .data import DataValidationError
from .observability import (
    log_http_event,
    record_http,
    record_model_load,
    record_recommendation,
    request_timer,
)
from .service import ModelNotReadyError, RecommendationService, UnsupportedInputError
from .settings import load_settings


SETTINGS = load_settings()
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
WEB_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Crop Advisor Prototype API",
    version="0.1.0",
    description=(
        "A prototype that predicts the recommended-crop label supplied in the training dataset. "
        "It does not independently validate which crop is optimal for a farm."
    ),
    docs_url=None if SETTINGS.is_production else "/docs",
    redoc_url=None if SETTINGS.is_production else "/redoc",
    openapi_url=None if SETTINGS.is_production else "/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(SETTINGS.allowed_hosts))
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def safe_request_validation_error(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    """Return validation details without echoing untrusted input values.

    FastAPI's default response includes the rejected input. Apart from being
    unnecessary disclosure, `NaN`/`Infinity` cannot be encoded as standards-
    compliant JSON in that default error payload.
    """

    safe_errors = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


class RecommendationRequest(BaseModel):
    """Only pre-decision fields permitted by the data contract are accepted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    district: Annotated[str, Field(min_length=1, max_length=100)]
    soil_color: Annotated[str, Field(min_length=1, max_length=100)]
    nitrogen: Annotated[float, Field(ge=0)]
    phosphorus: Annotated[float, Field(ge=0)]
    potassium: Annotated[float, Field(ge=0)]
    ph: Annotated[float, Field(ge=0, le=14)]
    rainfall: Annotated[float, Field(ge=0)]
    temperature: float
    top_k: Annotated[int | None, Field(default=None, ge=1, le=5)] = None


class RecommendationCandidate(BaseModel):
    crop: str
    probability: float


class RecommendationResponse(BaseModel):
    best_suitable_crop: str = Field(
        description=(
            "Top predicted Crop label from the prototype dataset; not independently verified "
            "as agronomically optimal."
        )
    )
    recommendations: list[RecommendationCandidate]
    highest_probability: float
    model_version: str
    dataset_maturity: str
    warnings: list[str]


class RecommendationOptionsResponse(BaseModel):
    dataset_maturity: str
    districts: list[str]
    soil_colors: list[str]


@app.middleware("http")
async def security_and_observability_middleware(request: Request, call_next):
    """Set basic safe headers, limit request size, and record anonymous telemetry."""

    request_id = request.headers.get("X-Request-ID", "")
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        request_id = uuid4().hex
    started_at = request_timer()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        else:
            if declared_size < 0 or declared_size > SETTINGS.max_request_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large."},
                )
            else:
                response = await call_next(request)
    elif request.method in {"POST", "PUT", "PATCH"}:
        # A proxy must still impose a byte limit, but rejecting a body-bearing
        # request with no declared size closes the chunked-transfer bypass for
        # this small JSON API.
        response = JSONResponse(
            status_code=411,
            content={"detail": "Content-Length is required for request bodies."},
        )
    else:
        response = await call_next(request)

    duration = record_http(request.method, request.url.path, response.status_code, started_at)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
    log_http_event(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_seconds=duration,
        request_id=request_id,
    )
    return response


@lru_cache(maxsize=1)
def get_service() -> RecommendationService:
    try:
        service = RecommendationService.from_artifact(
            SETTINGS.model_path,
            load_contract(SETTINGS.contract_path),
            expected_sha256=SETTINGS.model_sha256,
        )
    except Exception as error:
        record_model_load("failure")
        if isinstance(error, ModelNotReadyError):
            raise
        raise ModelNotReadyError("The controlled model artifact is not ready.") from error
    record_model_load("success")
    return service


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    """Serve the same-origin prototype form."""

    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


@app.get("/v1/options", response_model=RecommendationOptionsResponse, tags=["recommendations"])
def recommendation_options() -> dict[str, object]:
    """Expose trained categorical choices so the UI cannot drift from the model."""

    try:
        service = get_service()
    except ModelNotReadyError as error:
        raise HTTPException(status_code=503, detail="Model is not ready. Train it before serving.") from error
    categories = service.metadata["training_feature_metadata"]["categorical_values"]
    return {
        "dataset_maturity": service.metadata["dataset_maturity"],
        "districts": categories["district"],
        "soil_colors": categories["soil_color"],
    }


@app.get("/health", tags=["status"])
def health() -> dict[str, str]:
    """Liveness probe: the process can answer HTTP requests."""

    return {"status": "ok"}


@app.get("/ready", tags=["status"])
def ready() -> dict[str, str]:
    """Readiness probe: a valid trained artifact is available."""

    try:
        get_service()
    except ModelNotReadyError as error:
        raise HTTPException(status_code=503, detail="Model is not ready. Train it before serving.") from error
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint; place it on a private network in production."""

    if not SETTINGS.metrics_enabled:
        raise HTTPException(status_code=404, detail="Not found.")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/v1/recommendations",
    response_model=RecommendationResponse,
    tags=["recommendations"],
)
def create_recommendation(request: RecommendationRequest) -> dict:
    """Rank candidate crops using the versioned local model artifact."""

    try:
        service = get_service()
        values = request.model_dump(exclude={"top_k"})
        response = service.recommend(values, top_k=request.top_k)
        record_recommendation("success")
        return response
    except ModelNotReadyError as error:
        record_recommendation("model_unavailable")
        raise HTTPException(status_code=503, detail="Model is not ready. Train it before serving.") from error
    except (DataValidationError, UnsupportedInputError) as error:
        record_recommendation("invalid_input")
        raise HTTPException(status_code=422, detail=str(error)) from error


def run() -> None:
    """Run locally; production deployment should use an HTTPS reverse proxy."""

    import uvicorn

    uvicorn.run("crop_advisor.api:app", host="127.0.0.1", port=8000, reload=False)
