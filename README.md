# AI Observability & Monitoring Platform

Multi-service monorepo for an independently deployable AI monitoring MVP.

## Services

- `services/web`: React dashboard that talks only to `gateway-api`
- `services/gateway-api`: auth, dashboard, logs, and compare endpoints
- `services/ingest-api`: ingestion API for SDK log submission
- `services/processor`: background rollup and aggregation worker

## Shared Packages

- `packages/contracts`: shared event contracts and domain models
- `packages/sdk-python`: Python SDK for app instrumentation

## Infra

- `infra/compose`: local Docker Compose stack
- `infra/deploy`: per-service Kubernetes deployment templates

## Current MVP Flow

1. Your app uses `packages/sdk-python` to submit LLM request logs to `services/ingest-api`.
2. `ingest-api` validates the payload, redacts PII, and writes the event to the shared log store.
3. `services/processor` reads those raw logs and writes aggregate snapshots for dashboard metrics.
4. `services/gateway-api` serves auth, logs, detail, compare, and dashboard endpoints from shared storage.
5. `services/web` talks only to `gateway-api` and renders the user-facing dashboard.

## Local Development

The repo is structured so each service can be built and deployed separately. Local development uses shared infra and service containers:

```bash
docker compose -f infra/compose/docker-compose.yml up --build

The default local stack uses a shared file-backed data path between services so the full flow works without requiring the analytics adapters to be completed first. ClickHouse and Postgres are still provisioned in Compose and remain the target production backends.

## Verification

- Python services: run syntax checks with `python3 -m compileall packages services tests`
- Web smoke check: run `npm --workspace services/web test`
- Full stack: start Compose, send a log to `ingest-api`, run `processor`, then inspect results in `web`

## Git Remotes

Expected remotes for release:

- `origin` -> `https://github.com/BandanaPandey/ai-monitoring`
- `gitlab` -> `https://gitlab.com/bandanapandey11/ai-monitoring`
```

## Architectural Rules

- No service imports private runtime code from another service.
- Shared types, payload schemas, and job contracts live in `packages/contracts`.
- `web` only calls `gateway-api`.
- `ingest-api` owns write ingestion.
- `gateway-api` owns read/query and auth.
- `processor` owns derived metrics and background compute.
