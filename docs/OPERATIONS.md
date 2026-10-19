# Local operations: API, security, and monitoring

## Run locally

This section is for development/verification only. The service is not currently deployed to a cloud host.

First train the approved local artifact:

```powershell
crop-advisor-train
python app.py
```

Use `GET /health` for process liveness and `GET /ready` for model readiness. `/ready` returns `503` until a compatible artifact is present. The Prometheus `/metrics` endpoint is enabled only when explicitly configured in production; production defaults it off. Keep it on a private scrape network if enabled.

## Run with Docker

Docker Desktop was not available in this workspace during implementation, so run these checks on a machine with Docker Desktop in Linux-container/WSL2 mode and D: drive sharing enabled.

```powershell
# The model must already exist from crop-advisor-train.
./RUN_DOCKER.ps1

# In another terminal:
Invoke-RestMethod http://127.0.0.1:8000/ready

# Include the internal Prometheus service:
./RUN_DOCKER.ps1 -Monitoring
```

The helper computes the model SHA-256 and passes it into the container; production startup checks this hash before deserializing the joblib artifact. The compose file binds API port 8000 and Prometheus port 9090 only to `127.0.0.1`. It mounts the reviewed model artifact and contract read-only, runs as a non-root user, drops Linux capabilities, and uses a read-only filesystem with a small temporary filesystem.

Do not use short Windows bind-mount syntax for this repository: its path contains spaces and parentheses. The long bind syntax in `docker-compose.yml` avoids drive-letter parsing errors.

## Current telemetry

| Endpoint/metric | Purpose | Privacy rule |
| --- | --- | --- |
| `/health` | Is the process responding? | No request data. |
| `/ready` | Can a compatible controlled artifact be loaded? | No artifact details sent to clients. |
| `/metrics` | HTTP count/latency and recommendation outcome counters | Disabled by default in production; if enabled, keep on a private monitoring network. |
| JSON stdout log | method, bounded route, status, duration, request ID | Never log request body, soil values, district, farm coordinates, or IP address. |

`ops/prometheus/alerts.yml` alerts on API target loss, model readiness, high 5xx ratio, and p95 latency. Prometheus shows firing rules, but notification delivery requires an Alertmanager and configured receiver. For a hosted service, prefer provider-native telemetry unless you can operate a private Prometheus scrape path. Data drift and calibration monitoring wait for verified real-world outcome data.

## Security limits and next actions

Implemented now: typed input validation, finite-number rejection, extra-field rejection, strict allowed hosts, request-size declaration checks, no debug mode, generic model-load errors, security response headers, local-only container ports, non-root/read-only container settings, and no user-supplied model uploads.

Before public deployment, put the API behind an HTTPS reverse proxy that also enforces a body-size limit and rate limit. Use a real DNS allowlist, external authentication/authorization, a CORS allowlist for the eventual UI, secret management, dependency/image scanning, artifact signing or external hash verification, and a rollback runbook. Do not overwrite a live `model.joblib`; mount a new approved artifact version and roll/restart the service.
