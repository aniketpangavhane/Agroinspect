# Project roadmap and phase gates

Use this page to decide when the project is ready to move to the next phase. A phase is complete only when its evidence is available, not just when the code exists.

## Phase 0 — Reproducible prototype foundation

**Status: implemented in the repository; GitHub CI and Docker runtime verification are pending.**

- Declarative source contract, quality checks, cleaned data output, and source SHA-256 gate
- One preprocessing-plus-model pipeline and a single model artifact
- Random row evaluation plus leave-one-district-out evaluation
- Typed recommendation API, request validation, health/readiness, privacy-safe logs, Prometheus metrics
- Docker/Compose files with read-only model/contract mounts and a model hash check
- Learning guide and system design documentation

**Evidence:** `crop-advisor-audit` succeeds for the current 4,513-row file. A new CI workflow now runs tests, audit, training, container build, and a container smoke test on GitHub-hosted runners. The Docker CLI is not installed in this workspace, so the image has not been built locally; CI must pass before calling the container verified.

## Phase 1 — Establish the prototype data contract

**Status: dataset and target selected; prototype limitations remain.**

1. Use only `Crop_recommendation.csv`; the other CSV files are out of scope for this prototype.
2. Treat `Crop` as the supplied recommended-crop label. The model learns to predict that label; it does not verify that the crop is optimal for a farm.
3. Keep the declarative contract and source hash aligned with the exact CSV used for training.
4. Preserve unknown provenance/licence, collection method, measurement units, and time coverage as explicit limitations; do not fill them with guesses.
5. Keep the dataset maturity at `prototype_unverified` until the source and label-generation process are independently documented and reviewed.

**Exit condition:** the single-file schema, target meaning, exclusions, hash, and known limitations are recorded and reproducible. This completes the prototype data-selection decision, but does not qualify the dataset for production use.

## Phase 2 — Validate the recommendation task and model

**Status: not production-ready.**

- Keep the current prototype task explicit: predict the source-provided `Crop` recommendation label. Do not present label prediction as verified crop optimization; outcome-based yield or profit recommendations require different data and targets.
- For outcome-based recommendations, collect candidate-crop examples by location and season with actual yield, cost, and quality flags.
- Use time-based and geography-based holdouts that represent future and unseen cases; keep repeated plots/farms together in splits.
- Compare simple agronomic/rule baselines with ML; report macro F1, per-crop recall, top-k usefulness, calibration, and coverage.
- Review weak districts and rare crops with an agronomist; set explicit abstention rules for low data coverage.
- Record approval, version, and rollback decision for every model promotion.

**Current warning:** this local file produces about 0.996 random-holdout macro F1 but only about 0.194 mean macro F1 when holding out a district. The gap shows that the random split does not measure transfer to a different district.

**Exit condition:** prospective or independently held-out evidence supports the stated geography, season, crop set, and product claim, with agronomy review and an approved model card.

## Phase 3 — Make the product usable by farmers

**Status: a first prototype form exists; farmer usability testing is pending.**

- Test the new form, which matches the current API contract and gets district/soil choices from the trained model.
- Confirm data-entry guidance and units with local users; several units are unknown and the current form labels this rather than guessing.
- Improve confidence language and abstention behavior based on usability testing; model scores are not crop-success probabilities.
- Conduct usability tests with farmers/agriculture extension workers using realistic devices and connectivity.
- Support mobile layouts, accessible language, local crop names, low-bandwidth behavior, and a safe feedback path.
- Add accounts, farm history, and a database only if users need those features; define consent, retention, deletion, and access rules first.

**Exit condition:** target users can enter valid data, understand the recommendation limits, and recover from missing/out-of-scope information in usability sessions.

## Phase 4 — Verify deployment and operations

**Status: CI and Prometheus alert rules are implemented; runtime validation and cloud deployment are pending.**

- Run GitHub CI to build and smoke-test the image remotely. Local Docker is optional for development, not the intended hosting environment.
- Test container health/readiness, model hash mismatch, read-only mounts, non-root execution, restart, and rollback.
- Run `.github/workflows/ci.yml` on GitHub and review Dependabot updates; add an image-vulnerability scan before public hosting.
- Add HTTPS reverse proxy, real DNS host allowlist, rate limiting, external authentication if needed, and a rule denying public access to `/metrics`.
- Set uptime/latency/error/readiness alerts with an owner and recovery runbook.

**Exit condition:** reproducible deployment and rollback has been exercised in a controlled environment, with no direct public access to the prototype API.

## Phase 5 — Localization and assisted help

**Status: architecture planned; implementation follows a stable API and reviewed terminology.**

- Translate fixed UI/API messages and crop aliases with local reviewers; do not machine-translate agronomic instructions without review.
- Use stable message keys and explicit supported locales; localize labels/help/errors while keeping canonical API values and model class IDs unchanged.
- Add languages one at a time and test terminology, units, script rendering, and spoken/low-literacy usability.
- Add a chatbot only when it answers from approved agronomy content and current application data, cites its source, states uncertainty, and escalates high-risk questions.

**Exit condition:** translations and chatbot responses are reviewed by local domain experts and have clear fallback/escalation behavior.

## Current next step

The next engineering step is to commit and push these changes so GitHub-hosted CI can build and smoke-test the container; a local Docker daemon is not required. The repository is not hosted yet: choose a cloud account and access policy before creating a protected CD workflow. In parallel, establish source/label provenance and validation evidence before any farming-performance claim. Localization is planned for English, Marathi, and Hindi after text and API contracts are reviewed; see `docs/LOCALIZATION_PLAN.md`.
