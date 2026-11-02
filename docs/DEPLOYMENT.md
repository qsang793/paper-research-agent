# Production Deployment

This is the canonical release path. `docs/LOCAL_BACKEND_DEPLOYMENT.md` and the
Cloudflare tunnel guides are for local development or private demos only.

## Topology

```text
GitHub OAuth -> Vercel Next.js -> Railway FastAPI -> Railway Postgres/pgvector
                         |                 |
                         +-- trusted user -+-- persistent memory
```

- Frontend: one canonical Vercel project with root directory `web/`.
- Identity: Auth.js with GitHub OAuth. The backend does not store passwords.
- Backend: Railway service sourced from an immutable private GHCR image digest.
- Data: separate Railway Postgres services for staging and production.
- Network trust: browsers call Next.js routes only. Next.js authenticates the
  GitHub session and sends `X-Internal-Token` to FastAPI. `/health` stays public.

## Required Configuration

Store values in the named platform. Never commit or paste values into logs.

### Vercel

| Name | Scope |
|---|---|
| `AUTH_SECRET` | Preview and Production |
| `AUTH_GITHUB_ID` | Preview and Production |
| `AUTH_GITHUB_SECRET` | Preview and Production |
| `NEXT_PUBLIC_API_URL` | Environment-specific Railway HTTPS URL |
| `BACKEND_INTERNAL_TOKEN` | Environment-specific server-only value |

Register `https://<frontend-host>/api/auth/callback/github` for each fixed
frontend hostname. Use separate environment-scoped OAuth credentials when one
OAuth App cannot cover both hosts; never authorize ephemeral preview URLs.

### Railway API service

| Name | Production value/rule |
|---|---|
| `APP_ENV` | `production` |
| `BACKEND_INTERNAL_TOKEN` | Same environment-specific value as Vercel |
| `CORS_ORIGINS` | Exact canonical Vercel origin; no wildcard |
| `MEMORY_DATABASE_URL` | Private Postgres connection reference |
| `LLM_BACKEND` | Approved provider backend |
| Provider credentials | Railway secret variables only |
| Memory feature flags | Start `false`; enable in `docs/MEMORY_ROLLOUT.md` order |

Set the Railway health path to `/health` with a 300-second timeout. Configure
the service to pull the private GHCR package with a read-only `read:packages`
credential; do not reuse the GitHub Actions write credential.

Start each API environment with one replica, 2 vCPU, and 4 GB memory. Keep the
API and Postgres in the same Railway region, retain Railway deployment/runtime
logs, and change limits only from measured staging CPU, memory, and latency.
The owner who approves promotion also owns the pre-release database backup and
a restore drill into a separate database; record both references in the task.

### GitHub environments

Create repository environments `staging` and `Production` with these values:

- Secret: `RAILWAY_TOKEN`.
- Variables: `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`,
  `RAILWAY_ENVIRONMENT_ID`.
- Repository secret: `OPENROUTER_API_KEY` for Stage 4C live evaluation.

The current GitHub Hobby plan cannot require reviewers for a private repository
environment. `Production` is restricted to protected branches and production
deployment therefore remains a deliberate manual workflow dispatch.

## First Provisioning

1. Revoke and rotate any real credential that was ever stored in historical
   `.env`, `.env.railway`, or `web/.env.local.backup.*` files. The redacted
   repository scan must remain green; do not inspect or paste old values into a
   ticket or log.
2. Create one Railway project with independent `staging` and `production`
   environments.
3. Add one API service and one managed Postgres service in each environment.
4. Enable pgvector in each database and run the existing Postgres integration
   tests against the staging database.
5. Add platform variables above and keep all memory flags off initially.
6. Create a public Railway domain for each API service and set exact CORS
   origins.
7. Link the environment IDs and token to the matching GitHub environments.
8. Verify the canonical Vercel project before assigning its production domain;
   do not disconnect the duplicate project until rollback is proven.

## Release

1. Merge through a current pull request after `Secret hygiene`, `Backend
   contracts`, `Frontend contracts`, and `Docker runtime` pass.
2. Run **Backend Release** on `main` with `operation=publish`.
3. Copy the `sha256:...` digest from the workflow summary.
4. Run the same workflow with `operation=deploy-staging` and that digest.
5. Verify staging, then run `operation=deploy-production` with the identical
   digest. Do not rebuild between environments.
6. Promote the already-verified Vercel deployment to the canonical domain.

Railway must report the deployment healthy before traffic moves. Record the
Git SHA, image digest, Railway deployment ID, and Vercel deployment ID in the
active `.codex/tasks/` task.

## Smoke Checks

Use only variable names in shell history; do not print their values.

```bash
curl --fail --silent "$API_URL/health"
curl --fail --silent \
  -H "X-Internal-Token: $BACKEND_INTERNAL_TOKEN" \
  "$API_URL/api/features"
curl --fail --silent "$FRONTEND_URL/auth/login"
```

Then verify through the browser:

1. GitHub sign-in returns to `/chat`.
2. An unauthenticated `/api/chat` request returns 401.
3. A research turn streams with `x-vercel-ai-ui-message-stream: v1` and renders
   traceable citations.
4. `/api/memory/features` reports `postgres` before any memory flag advances.
5. A second user cannot read, overwrite, or delete another user's session.

Follow `docs/MEMORY_ROLLOUT.md` for flags, Postgres row checks, deletion, and
rollback. Run the live router baseline and candidate experiment before changing
the production router model.

## Backup and Rollback

Before production promotion, record a restorable Postgres backup and the
current Railway image digest and Vercel deployment ID.

- Backend regression: reconnect the prior GHCR digest in Railway and wait for
  `/health` before confirming rollback.
- Frontend regression: promote the previous Vercel deployment.
- Memory regression: disable only the most recently enabled memory flag; retain
  Postgres data.
- Database regression: stop promotion, preserve the failed deployment, and
  restore into a new database before changing the production database.

Rollback immediately for sustained 5xx errors, database unavailability,
cross-user session access, broken streaming/citations, or material latency
regression. Recheck immediately, after 15 minutes, after one hour, and the next
business day.
