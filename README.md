# tryfitted

This repo is scaffolded to match the phased plan in `DevelopmentPlan.MD`.

## What’s implemented
- Monorepo structure (`apps/*`, `packages/*`) with shared zod contracts in `packages/shared`
- API (`apps/api`) with:
  - `GET /health`
  - `POST /v1/uploads/presign` (MinIO presigned PUT URL)
  - `GET /v1/fixtures/garments`
  - `POST /v1/tryon/fit` (fixture-driven fit engine)
  - BullMQ no-op queue worker scaffold
- Fit Lab (`apps/web`) internal UI that calls `POST /v1/tryon/fit`
- Local infra (`infra/docker-compose.yml`) for Postgres + Redis + MinIO
- Avatar System v1 (Phase 1 implementation; validation pending) with:
  - Prisma schema + migration in `apps/api/prisma/`
  - Avatar job endpoints: `POST /v1/avatar/jobs`, `GET /v1/avatar/jobs/:id`, `GET /v1/avatar/current`, `PATCH /v1/avatar/jobs/:id/status`
  - Python worker scaffold in `services/avatar-worker/` that consumes the `avatar_build` BullMQ queue and updates job status
  - Avatar Lab (`apps/web`) UI for uploading photos and polling job status

## Prereqs
- Node.js 20+
- pnpm 9+ (`corepack enable`)
- Docker + Docker Compose

## Local dev (recommended)
```bash
pnpm install
pnpm dev
```

Then:
- API: `http://localhost:3001/health`
- Web (Fit Lab + Avatar Lab): `pnpm --filter @tryfitted/web dev` (defaults to `http://localhost:5173`)
- Avatar worker (separately): `python services/avatar-worker/src/worker.py` (requires Python deps; see `services/avatar-worker/README.md`)
  - Note: the in-app GLB viewer proxies local MinIO through Vite at `http://localhost:5173/__minio/...`

If `pnpm dev` fails with a permissions error, run `chmod +x scripts/dev.sh` once.

## Docker (API inside compose)
```bash
docker compose -f infra/docker-compose.yml --profile full up -d --build
```
