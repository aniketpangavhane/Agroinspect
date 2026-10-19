# System design

## Product boundary for the first release

The current system is a **crop-label prediction prototype** for five observed Maharashtra districts. It predicts the `Crop` label supplied by the dataset and returns a ranked shortlist; this is not independent proof of agronomic suitability, crop success, or a fertiliser dose. Unknown districts and soil colours are rejected instead of silently one-hot encoding them as nothing.

## Implemented data-to-API path

```text
User-supplied CSV (read-only)
        |
        v
Declarative JSON contract --> validation, cleanup, leakage checks --> curated CSV + quality report
        |
        v
Sklearn preprocessing pipeline + classifier --> evaluation --> one versioned model bundle + model card
        |
        v
Same-origin HTML/CSS/JS form
        | GET /v1/options (supported categories)
        | POST /v1/recommendations (field inputs)
        v
FastAPI validation + scope/range checks --> top-three candidates + warnings
```

`Fertilizer` and `Link` travel through the quality audit only; neither is a model input. This separation prevents leakage from being introduced later by accident.

## Core design choices

| Concern | Decision | Why |
| --- | --- | --- |
| Data semantics | JSON data contract | Schema, role, range, and canonical-name changes are reviewed independently of code. |
| Raw data | Read only | Training never mutates the source CSV. |
| Cleaning | Generated curated dataset | Whitespace/category cleanup is reproducible and auditable. |
| ML artifact | One joblib bundle | Pipeline, preprocessor, and class labels cannot drift apart. |
| Evaluation | Random baseline plus district holdout | Makes the optimistic demo metric visibly different from geographic generalization. |
| Serving | Typed HTTP API | The API accepts only declared pre-decision inputs and rejects unknown scope. |
| Product language | Ranked candidates + limitations | Avoids presenting probability as agronomic certainty. |

## Target architecture after the data gate

```text
Web/mobile clients
       |
HTTPS + locale-aware API + authentication
       |
Recommendation service -------- PostgreSQL/PostGIS (accounts, farms, consent, feedback)
       |                                  |
Versioned approved model                  encrypted backups + audit trail
       ^
Training pipeline <--- versioned raw/curated data + source manifests
       |
Model registry + agronomist approval gate
       |
Metrics/logs + data quality + drift monitoring
```

Start as a modular monolith. Do not build microservices, a feature store, or Kubernetes until traffic and team size justify them.

## Security design

The current local/container baseline implements: typed JSON validation, finite-number rejection, strict host allowlists, no debug mode, declared request-size checks, generic artifact-load failures, safe response headers, and a non-root/read-only container profile. It intentionally has no permissive CORS policy and no model-upload endpoint.

Before any public deployment, add:

- HTTPS behind a reverse proxy; production debug mode off
- Environment-based secrets, never committed `.env` files
- OAuth/OIDC authentication and role-based authorization once accounts exist
- Strict request size limits, CORS allowlist, rate limiting, and CSRF protection for cookie-based forms
- Dependency scanning, pinned builds, non-root Docker user, and image scanning
- No loading of user-provided pickle/joblib files; only controlled build artifacts
- Consent, retention/deletion policy, and minimal logging for farm locations and personal data

## Observability design

The current `/health` and `/ready` endpoints are deployment probes. `/metrics` exposes low-cardinality Prometheus HTTP and recommendation-outcome metrics when enabled; it defaults off in production. The API emits structured JSON logs with method, bounded route, status, duration, and request ID. It does not log request bodies, locations, or soil values. The Compose monitoring profile keeps Prometheus on the private Docker network and binds its UI only to localhost.

The next layer should add model version, validation failure category, out-of-range field, and approved rollout metrics. Log only event metadata by default, not farm coordinates or full requests.

After verified outcomes exist, monitor data drift, prediction drift, calibration, yield/outcome error, and fairness across districts/smallholder contexts. Alerting must lead to an owner and a runbook, not just a dashboard.

## Deployment sequence

1. Validate data and train locally.
2. Add unit/API tests and CI checks.
3. Containerize API with a non-root image and mount only an approved model bundle.
4. Deploy privately behind HTTPS; test health/readiness and rollback.
5. Add databases/accounts only when users need saved farms or feedback.
6. Add translations from approved message keys and locally reviewed crop names.
7. Add a chatbot only if it is grounded in reviewed agronomy content and can decline unsafe requests.
