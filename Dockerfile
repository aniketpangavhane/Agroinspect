# syntax=docker/dockerfile:1
# Build a small, immutable API image. The approved model and data contract are
# deliberately mounted at runtime; they are not baked into the image.
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install --no-compile .

FROM python:3.14-slim AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    CROP_ADVISOR_ENV=production \
    CROP_ADVISOR_ALLOWED_HOSTS=localhost,127.0.0.1 \
    CROP_ADVISOR_MAX_REQUEST_BYTES=65536 \
    CROP_ADVISOR_MODEL_PATH=/models/model.joblib \
    CROP_ADVISOR_CONTRACT_PATH=/contracts/maharashtra_crop_recommendation.v1.json

WORKDIR /app
RUN groupadd --system --gid 10001 cropadvisor \
    && useradd --system --uid 10001 --gid cropadvisor \
        --home /nonexistent --shell /usr/sbin/nologin --no-create-home cropadvisor

COPY --from=builder /opt/venv /opt/venv

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2).read()"]

CMD ["python", "-m", "uvicorn", "crop_advisor.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--limit-concurrency", "100", "--timeout-keep-alive", "5"]
