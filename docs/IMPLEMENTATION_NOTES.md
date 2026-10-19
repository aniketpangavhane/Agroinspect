# Implementation notes — first foundation slice

## Why the legacy code could not be reused

The former three training scripts expect the old `N`, `P`, `K`, `ph`, and `label` schema. The newly supplied file uses `District_Name`, `Soil_color`, `Nitrogen`, `Phosphorus`, `Potassium`, `pH`, `Rainfall`, `Temperature`, and `Crop`. The prior Flask form also loads stale pickles and has a hard-coded eleven-crop mapping. It would either fail to train or serve a model unrelated to the new data.

## Changes made

| Location | Change | Purpose |
| --- | --- | --- |
| `data/contracts/maharashtra_crop_recommendation.v1.json` | Added data contract | Defines canonical schema, ranges, roles, exclusions, and production blockers. |
| `data/metadata/maharashtra_crop_recommendation.v1.json` | Added source manifest | Records local-file hash and the missing provenance that must be resolved. |
| `configs/training.maharashtra.v1.json` | Added run configuration | Keeps paths, model settings, validation, and confidence policy outside code. |
| `src/crop_advisor/data.py` | Added validation/cleaning | Converts source names to canonical names, trims `Red `, validates values, flags leakage, writes reports. |
| `src/crop_advisor/training.py` | Added one training pipeline | Fits preprocessing and classifier together; produces metrics, metadata, model card, and one artifact. |
| `src/crop_advisor/service.py` | Added inference boundary | Enforces scope and returns ranked candidates with warnings. |
| `src/crop_advisor/api.py` and `app.py` | Replaced stale Flask serving | Provides typed `/v1/recommendations`, `/health`, `/ready`, and `/docs`; no debug mode or raw exceptions. |
| `src/crop_advisor/settings.py` and `observability.py` | Added runtime safeguards | Adds environment-based configuration, host and size limits, security headers, structured privacy-safe logs, and Prometheus metrics. |
| `Dockerfile`, `docker-compose.yml`, `ops/prometheus/` | Added local deployment path | Runs the API non-root with immutable mounted model/contract; optional Prometheus stays private. |
| `.github/workflows/ci.yml`, `.github/dependabot.yml`, `ops/prometheus/alerts.yml` | Added delivery and operations baseline | GitHub CI audits/tests/trains/builds/smoke-tests on a hosted runner; dependency update PRs and API availability/readiness/error/latency alert rules are configured. Cloud deployment remains gated on account and security choices. |
| `RUN_DOCKER.ps1` and `src/crop_advisor/settings.py` | Added artifact integrity gate | Computes the local model hash and requires production API startup to verify it before loading. |
| Dataset contract, training metadata, recommendation response, and roadmap | Clarified prototype target | Uses only `Crop_recommendation.csv`; records that `Crop` is the supplied recommended-crop label and returns its top prediction without asserting it is independently verified as optimal. |
| `src/crop_advisor/static/`, `src/crop_advisor/api.py`, and `pyproject.toml` | Added first farmer-facing prototype form | Serves packaged same-origin UI assets, loads supported categories from `/v1/options`, posts validated fields to `/v1/recommendations`, and displays rankings and warnings with accessible status messages. |
| `pyproject.toml`, `requirements.txt`, `.gitignore` | Added packaging and output hygiene | Makes commands reproducible and prevents generated artifacts from being committed accidentally. |
| `docs/` | Added design and learning docs | Explains scope, next system layers, and what to study. |

## Intentionally not done yet

- No claim that the new data is production-grade
- No database, login, farmer profiles, payment, chatbot, translations, or public deployment
- No cloud infrastructure or public deployment before model/data validation is trusted
- No automatic CD, because cloud project, artifact bucket, account permissions, and public/private access choice have not been supplied
- No change to the raw CSV, old notebook, legacy scripts, existing pickle artifacts, or untracked run scripts

Those are later milestones, not omissions. Building them before data provenance and model validity would make an unsafe system look more complete than it is.
