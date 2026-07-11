# PulseGrid

Open-source, multi-tenant, globally distributed uptime monitoring — availability,
latency and SSL certificate health for your services, checked from anywhere you
can run a container. Self-hosted alternative to services like UptimeRobot.

## Architecture

```
                        ┌─────────────────────────── Kubernetes ───────────────────────────┐
┌──────────┐   HTTPS    │  ┌──────────┐    ┌───────────────┐     ┌─────────┐   ┌────────┐  │
│ Browser  ├────────────┼─▶│ frontend │───▶│ web (Django +  │────▶│ Postgres│   │ Redis  │  │
└──────────┘            │  │ (nginx + │    │ DRF + allauth) │     └─────────┘   └───┬────┘  │
                        │  │  React)  │    └───────▲───────┘                        │       │
      Authentik ◀───────┼──┴──────────┘            │              ┌───────────┐     │       │
      (OIDC SSO)        │                          │              │ scheduler ├─────┤       │
                        │                          │              └───────────┘     │       │
                        │                          │              ┌────────────┐    │       │
                        │                          │              │ dispatcher ├────┘       │
                        │                          │              └─────┬──────┘            │
                        └──────────────────────────┼────────────────────┼───────────────────┘
                                          claim /  │ results            └──▶ email / webhooks
                     ┌─────────────────────────────┴─────────────────────────────┐
                     │ workers — one container per region, anywhere in the world │
                     │   eu-west ─ us-east ─ ap-south ─ …  (outbound HTTPS only) │
                     └────────────────────────────────────────────────────────────┘
```

**Control plane** (`controlplane/`) — Django 5 + DRF. Multi-tenant (organizations),
session-authenticated SPA API, and a token-authenticated worker API. Login via
username/password or Authentik SSO (django-allauth headless, OpenID Connect).
Three processes from one image:

- `web` — gunicorn serving the API, admin and auth.
- `scheduler` — scans for due monitors (`SELECT … FOR UPDATE SKIP LOCKED`, safe to
  run replicated) and fans out self-contained check tasks onto one Redis list per
  region. Intervals from 1 minute to 24 hours per monitor.
- `dispatcher` — consumes the notification queue and delivers alert emails and
  webhooks, decoupled from result ingestion.

**Worker** (`worker/`) — a small asyncio agent. Claims task batches over HTTPS
(outbound only — runs behind NAT), executes HTTP/TCP checks with bounded
concurrency, measures DNS/total latency, captures SSL certificate expiry, and
posts results back. Region and identity come from its token.

**Frontend** (`frontend/`) — React + TypeScript SPA (Vite, TanStack Query,
Tailwind, Recharts). Responsive for mobile and desktop: dashboard, per-region
latency charts, uptime stats, monitor management, alert history, notification
channels.

**Alerting** — a region marks a monitor down after N consecutive failures
(`failure_threshold`); the monitor alerts once M regions confirm
(`confirmations`). Recovery and SSL-expiry events notify the organization's
email/webhook channels.

## Quick start (local)

```bash
docker compose up --build
```

- UI: http://localhost:5173 (auto-logged-in as `admin` via `DEV_AUTO_LOGIN`)
- API/admin: http://localhost:8000/admin (admin / admin)

Start a local monitoring worker:

```bash
docker compose exec controlplane python manage.py create_worker_token --name local --region local
WORKER_TOKEN=pgw_… docker compose --profile worker up -d worker
```

## Running the tests

```bash
# control plane
cd controlplane && pip install -r requirements-dev.txt && pytest

# worker
cd worker && pip install -r requirements-dev.txt && pytest

# frontend
cd frontend && npm ci && npm test && npm run build
```

CI (`.github/workflows/ci.yaml`) runs all three suites plus ruff, a
migrations-are-committed check, and `helm lint` on every push/PR.

## Deploying to Kubernetes (ArgoCD)

Container images are built by `.github/workflows/build.yaml` on pushes to
`main` and on `v*` tags, and pushed to `registry.vels.online/pulsegrid/…`
(set `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` repo secrets).

Point ArgoCD at `deployment/chart/pulsegrid`. Minimum values to override:

```yaml
config:
  allowedHosts: pulsegrid.example.com
  csrfTrustedOrigins: https://pulsegrid.example.com
  frontendUrl: https://pulsegrid.example.com
  authentik:
    serverUrl: https://auth.example.com/application/o/pulsegrid/
ingress:
  host: pulsegrid.example.com
secrets:
  existingSecret: pulsegrid-secrets   # DJANGO_SECRET_KEY, DATABASE_URL,
                                      # AUTHENTIK_CLIENT_ID/SECRET, EMAIL_*
```

The chart ships web/scheduler/dispatcher/frontend Deployments, a pre-sync
migration Job (`ensure_regions` included), a nightly result-retention CronJob,
an optional single-node Redis, an optional dev Postgres, ingress and an HPA.
Database migrations run automatically via ArgoCD PreSync hooks.

In Authentik, create an OAuth2/OpenID provider with redirect URI
`https://<host>/accounts/openid_connect/authentik/login/callback/` and put the
issuer URL in `config.authentik.serverUrl`.

## Adding a monitoring region

1. Add the region (`kubectl exec deploy/…-web -- ./entrypoint.sh ensure_regions`
   after extending `config.regions`, or via the admin).
2. Issue a token:
   `./entrypoint.sh create_worker_token --name fra-1 --region eu-central`
3. On any host in that region, drop the token into `.env` next to
   `workers/docker-compose.yaml` and `docker compose up -d`.

Workers only need outbound HTTPS to the control plane — no inbound ports, no
VPN, no database access. Add capacity in a region by running more replicas
with the same or separate tokens.

## Scaling notes

- **Checks**: tasks are self-contained JSON on per-region Redis lists; workers
  batch-claim (`WORKER_MAX_BATCH`) and run up to `WORKER_CONCURRENCY` checks
  concurrently. One small worker sustains hundreds of 1-minute monitors.
- **Scheduler**: batched scans with row locking; replicas don't double-schedule.
- **Ingestion**: results are written append-only (`CheckResult`) with rolling
  per-region state; alerting happens on state transitions only.
- **Retention**: `purge_results` trims raw results (default 30 days) nightly.

## Repository layout

```
controlplane/   Django control plane (API, scheduler, dispatcher)
worker/         Globally deployable monitoring agent
frontend/       React SPA
deployment/     Helm chart (ArgoCD-ready)
workers/        docker-compose for standalone worker fleets
.github/        CI + container build workflows
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
