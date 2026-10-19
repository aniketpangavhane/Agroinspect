# Hosting and Play Store path

## What exists now

This repository currently contains a browser form and a Python/FastAPI service. The service is container-ready and exposes health/readiness probes, structured privacy-conscious logs, and optional Prometheus metrics. It is not an Android application, and a Docker image is not an artifact that can be uploaded to Google Play.

CI in `.github/workflows/ci.yml` runs tests, audits the configured CSV, trains the model bundle in a clean runner, validates Compose, builds the image, and smoke-tests the hardened container. It deliberately does not publish an image or deploy a public service. Public deployment needs cloud ownership, a reviewed model, an access/rate-limit design, and secrets that are not available in this repository.

## Hosting recommendation for a controlled web demo

For the first hosted demo, use one managed container service rather than Kubernetes. Google Cloud Run is a reasonable option if you want to stay in Google Cloud: it accepts container images and can mount Cloud Storage read-only for the model and contract. Give the runtime service identity read-only access to only the required artifact bucket. See Google's [Cloud Run deployment guide](https://docs.cloud.google.com/run/docs/deploying) and [Cloud Storage volume mount guide](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts).

Before deploying, complete these tasks:

1. Run GitHub CI to build and smoke-test the container on a hosted runner. Local Docker is optional for development; it is not the intended hosting environment.
2. Review the data source and licensing, measurement units, label generation, and intended geographic/seasonal scope. Independently validate the model claim before presenting it as real farming advice.
3. Decide whether the hosted prototype is private for a demo or public. Do not make it public until authentication or abuse controls, rate limiting, HTTPS, privacy notices, and an incident/rollback owner are in place.
4. Train an explicitly approved model bundle, store the model and contract in a private versioned bucket, and record the SHA-256 of the exact model file.
5. Create a cloud project, enable billing with a budget alert, create a least-privilege service identity and artifact repository, then deploy a pinned image by digest. Set `CROP_ADVISOR_ALLOWED_HOSTS` to the exact deployed/custom hostname, `CROP_ADVISOR_MODEL_SHA256` to the approved hash, and `CROP_ADVISOR_METRICS_ENABLED=false` for a publicly reachable service.
6. Use provider-native service metrics and structured logs initially. Cloud Run has built-in service observability; keep `/metrics` disabled unless a private scraper can reach it. Do not open the Prometheus UI to the internet. Cloud Run usage and associated storage/network/build services can incur charges; check current [pricing](https://cloud.google.com/run/pricing) and set budgets before hosting.

The local Compose stack is a development/operations learning tool, not the production host: API and Prometheus are loopback-bound, the model is mounted read-only and hash-checked, and the container runs non-root with a read-only filesystem. Prometheus alert rules cover target availability, model readiness, server error ratio, and p95 latency. Rules become visible in Prometheus; email/chat notifications require a separately configured Alertmanager and receiver.

## Optional public EC2 demo (not production)

The Compose `public` profile adds Caddy as an HTTPS reverse proxy. The API and Prometheus ports remain loopback-only; Caddy publishes only web ports 80/443. Caddy obtains and renews a public certificate when the configured hostname resolves to the EC2 public IP and inbound HTTP/HTTPS reach the instance. See the [Caddy HTTPS prerequisites](https://caddyserver.com/docs/quick-starts/https).

For a no-cost demo hostname, create a subdomain with [DuckDNS](https://www.duckdns.org/), point its A record at the instance's current public IPv4 address, and set `CROP_ADVISOR_DOMAIN=your-name.duckdns.org` in an EC2-local `.env` file (ignored by Git). If EC2's public IPv4 changes after stopping/starting the instance, update the DNS record. Do not put a DuckDNS account token in Git or send it in chat.

After pushing this configuration, add inbound TCP 80 and 443 rules to the EC2 security group; keep SSH (22) restricted to your own IP and do not open 8000 or 9090. Set `CROP_ADVISOR_MODEL_SHA256` in the EC2 shell, then start `docker compose --profile public up -d`; add `--profile monitoring` if Prometheus is also needed. Caddy returns 404 for `/metrics`, while Prometheus scrapes it over the private Docker network.

This profile is deliberately open to anyone, as a demo choice: it has no user login and no application-level rate limiter. Public traffic can consume the instance's CPU and AWS data transfer. Monitor usage and stop the profile when it is not needed. Before calling the service production-ready, add authentication or abuse controls, rate limiting, privacy review, and an operational owner as described above.

## CD decision

The current workflow is CI, not automatic CD. A deployment action should only be added after you choose the hosting account, service name/region, public-vs-private access, artifact storage, and GitHub-to-cloud authentication. Use OIDC/workload identity federation instead of a long-lived service-account key, protect deployment with a GitHub environment approval, deploy immutable image digests, and retain a one-step rollback. This is an intentional gate, not a missing line of YAML: a workflow that silently creates public infrastructure would be unsafe and not reproducible without your account details.

## Android / Play Store work

When hosted, the Dockerized Python API remains separate from the Android client; the app calls the API over HTTPS. For a recruiter-quality and useful mobile app, add a native Kotlin/Jetpack Compose client (or Flutter if you want cross-platform) with accessible field entry, local unit help, clear recommendation limitations, resilient network/error states, and user-tested localized content. Avoid shipping only a WebView wrapper; Google Play requires stable, meaningful app functionality and disallows limited-functionality apps ([functionality policy](https://support.google.com/googleplay/android-developer/answer/9898783)). See the [localization plan](LOCALIZATION_PLAN.md) for English, Marathi, and Hindi language handling.

For publishing, plan for an Android App Bundle (`.aab`) and Play App Signing for new apps ([AAB guidance](https://developer.android.com/guide/app-bundle/faq)). As of August 31, 2026, new apps and updates must target Android 16 / API 36 or higher ([target API policy](https://developer.android.com/google/play/requirements/target-sdk)). A new personal developer account created after November 13, 2023 must complete a closed test with at least 12 opted-in testers continuously for 14 days before applying for production access ([testing requirement](https://support.google.com/googleplay/android-developer/answer/14151465)). Play requires accurate Data Safety declarations and a privacy policy ([Data Safety requirements](https://support.google.com/googleplay/android-developer/answer/10787469)). Full Play distribution currently requires a one-time US$25 developer registration fee and identity verification ([account setup](https://support.google.com/googleplay/android-developer/answer/6112435)).

Also prepare the package name, app icon/screenshots/store listing, content-rating and app-content declarations, support contact, privacy policy, and any access instructions reviewers need. Do not declare data practices until they match the actual Android client, API, hosting logs, and third-party SDKs.

Suggested order: hosted private API demo → native Android client against staging API → internal/closed testing → privacy/Data Safety and store listing review → production access → public release. Build the Android app only after the API schema and model scope stop changing frequently.

## Recruiter presentation

Lead with engineering and learning outcomes, not unsupported model claims. A concise project summary:

> Built a crop-label prediction system end to end: declarative data validation, repeatable scikit-learn training and evaluation, a typed FastAPI service, a responsive client, container hardening, CI smoke tests, and privacy-conscious Prometheus monitoring. The model predicts the supplied crop label within the dataset's current scope; the project separates operational reliability from agronomic validation.

Show the API contract, CI run, Dockerfile hardening, alerts, and model evaluation split. Be ready to explain why the random-split score is not evidence of performance in a new district, and what real outcome/time/geography data would be needed to validate that claim. This demonstrates sound engineering judgment rather than disguising project scope.
