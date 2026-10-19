# Crop Advisor — deployable ML prototype

Portfolio project demonstrating an end-to-end ML service: declarative data validation, repeatable training/evaluation, a typed FastAPI API, responsive web UI, a hardened container, CI smoke tests, and privacy-conscious monitoring. It uses only `Crop_recommendation.csv`, covering the five Maharashtra districts represented there: Kolhapur, Pune, Sangli, Satara, and Solapur. The model predicts the supplied `Crop` recommendation label; it does not predict yield or profit.

The project distinguishes software reliability from evidence about farming outcomes. Dataset provenance, licence, measurement units, and seasonal/field validation are not established, so the current model scope is a prototype and must not be described as independently validated farm advice. The service can be deployed after the data, access-control, and operational gates in [hosting and Play Store guidance](docs/DEPLOYMENT_AND_PLAY_STORE.md) are addressed.

## What is implemented now

- Declarative data contract with canonical field names and validation rules
- Dataset audit that normalizes categorical whitespace without editing the raw CSV
- One reproducible scikit-learn pipeline, including preprocessing and class mapping
- Stratified and leave-one-district-out evaluation
- Versioned model bundle, metadata, data-quality report, and generated model card
- Typed FastAPI endpoint with input validation, scope checks, top-three results, and health/readiness endpoints
- Mobile-friendly same-origin prototype form; its district and soil-colour choices come from the trained model
- Non-root/read-only Docker image, local Compose stack, private Prometheus profile, and actionable alert rules
- GitHub Actions CI for tests, data audit, training, container build, and hardened-container smoke test

Read [the system design](docs/SYSTEM_DESIGN.md), [dataset review](docs/DATASET_REVIEW.md), [project roadmap](docs/ROADMAP.md), [localization plan](docs/LOCALIZATION_PLAN.md), and [learning guide](docs/LEARNING_GUIDE.md) before treating model metrics as product quality.

## Quick start (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Inspect and clean the local source file into an ignored curated output.
crop-advisor-audit

# Validate, evaluate, and train the single model bundle.
crop-advisor-train

# Start the API at http://127.0.0.1:8000
python app.py

# Optional development check: run the hardened container locally (Docker Desktop required)
./RUN_DOCKER.ps1
```

These commands are for development and verification only; they do not deploy the service. Open `http://127.0.0.1:8000/` for the prototype form or `/docs` to inspect the development API. The model must be trained first; until then `/ready` and the form's choice-loading endpoint correctly report that it is not ready. Production hosting and the separate Android/Play Store path are described in [deployment guidance](docs/DEPLOYMENT_AND_PLAY_STORE.md).

Example request:

```powershell
$body = @{
  district = "Kolhapur"
  soil_color = "Black"
  nitrogen = 75
  phosphorus = 50
  potassium = 100
  ph = 6.5
  rainfall = 1000
  temperature = 20
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/recommendations" `
  -ContentType "application/json" `
  -Body $body
```

## Where things live

```text
configs/                         Training-run configuration
data/contracts/                  Declarative source/schema contract
data/metadata/                   Dataset provenance manifest
data/raw/                        Future immutable source snapshots
data/curated/                    Generated canonical data (ignored by Git)
src/crop_advisor/data.py         Validation and cleaning
src/crop_advisor/training.py     Training, evaluation, artifacts
src/crop_advisor/service.py      Safe inference logic
src/crop_advisor/api.py          HTTP API
src/crop_advisor/static/         Packaged prototype HTML, CSS, and JavaScript
artifacts/                       Generated reports/model (ignored by Git)
docs/                            Design, learning, data review, change notes
tests/                           Regression tests
```

The legacy `train_model*.py`, `model.pkl`, `minmaxscaler.pkl`, `crop_mapping.txt`, `index.html`, and notebook are retained for reference only. They use the old incompatible schema and must not be used to train or serve the new dataset.

## Next milestones

1. Run the new CI workflow in GitHub and validate the Docker/Compose stack on a machine with Docker installed.
2. Verify source/licence, measurement units, time coverage, and how the supplied crop labels were generated; add real outcomes and expert review before making farm-performance claims.
3. Choose a cloud account and hosting/access model; add a protected deployment workflow only after private artifact storage, rate limiting, privacy controls, and rollback are ready.
4. Build a native Android client and validate the service and user experience with intended users before any Play Store release.
5. Localize reviewed UI/API messages and crop names in English, Marathi, and Hindi; add an agronomy-grounded assistant only after those translations and the recommendation contract are stable.
