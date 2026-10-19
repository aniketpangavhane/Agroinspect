# Learning guide: understand the refactor by running it

## Lesson 1 — A dataset is a contract, not just a CSV

Open `data/contracts/maharashtra_crop_recommendation.v1.json`. Each field says what the source calls it, what the application calls it, whether it is a feature/target/excluded field, and which values are physically invalid. That is a declarative data model.

Run:

```powershell
crop-advisor-audit
```

Then read `artifacts/maharashtra_crop_suitability_v1/data_quality_report.json`. Notice that `Red ` was normalized to `Red`, but the raw source file was not edited.

**Exercise:** Add a deliberately invalid pH to a disposable copy of the CSV, point a copied training config at it, and observe validation fail before model training begins.

## Lesson 2 — Prevent leakage

Read the excluded `fertilizer` and `reference_link` fields in the contract and [dataset review](DATASET_REVIEW.md). A feature can improve an offline score yet make a real product worse if it would not be known when a farmer asks for a recommendation.

**Exercise:** Explain why a future crop's fertiliser choice cannot be an input to choosing that crop.

## Lesson 3 — Train one pipeline, not separate files

`src/crop_advisor/training.py` builds a `ColumnTransformer` plus `RandomForestClassifier` inside one `Pipeline`. It stores both together in `model.joblib`.

Run:

```powershell
crop-advisor-train
```

Read the generated `MODEL_CARD.md` before reading only the accuracy number. Compare random-holdout macro F1 with leave-one-district-out macro F1. The gap teaches why a random split can exaggerate real-world quality.

## Lesson 4 — A model must have a serving contract

`src/crop_advisor/api.py` is the externally visible contract. It accepts typed JSON, rejects extra fields, validates pH and non-negative nutrients, and passes only valid values to `src/crop_advisor/service.py`.

Start it with `python app.py`, open `/` for the form or `/docs` for the API explorer, and submit a supported request. Try an unknown district: rejecting it is safer than inventing a confident-looking answer.

## Lesson 5 — Build production layers in order

The local form is served by FastAPI from `src/crop_advisor/static/`. It calls the same-origin `/v1/options` endpoint to get supported district and soil categories, then submits the exact API request schema. Keeping the UI in the same origin avoids a separate CORS setup for this prototype; it does not replace authentication, HTTPS, or usability review for a public service.

**Exercise:** Open the browser developer tools, observe `/v1/options` and `/v1/recommendations`, and compare their payload fields with `RecommendationRequest` in `src/crop_advisor/api.py`. Why should the browser never decide which districts the model supports?

Learn these in this sequence:

1. Python packaging, virtual environments, Git, and automated tests
2. CSV/SQL data modelling, provenance, units, and data quality
3. ML leakage, class imbalance, spatial/temporal splits, calibration, and model cards
4. FastAPI, JSON, HTTP status codes, and API testing
5. Docker, CI/CD, secrets, HTTPS, and OWASP web security
6. PostgreSQL/PostGIS, consent/privacy, metrics, logs, and drift monitoring
7. Localization and accessible, low-bandwidth user experience
8. Agronomy validation and human feedback loops

Do not jump to a chatbot before you can explain each model input, its source, its unit, and what the model is allowed to claim.
