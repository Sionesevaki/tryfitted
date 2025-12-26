# Coolify (VPS) Deployment

Target: run the “always-on” services on a cheap VPS via Coolify, and run the GPU `avatar-worker` separately on RunPod.

## What runs on Coolify

- Postgres (API database)
- Redis (BullMQ queue)
- MinIO (S3-compatible object storage)
- API (`apps/api`)

## CI/CD: how updates flow

1. Push to `main`
2. GitHub Actions builds and pushes images to GHCR:
   - `ghcr.io/<owner>/tryfitted-api:main` (and `:sha-...`)
   - `ghcr.io/<owner>/tryfitted-avatar-worker:main` (and `:sha-...`)
3. Coolify pulls `tryfitted-api:main` and redeploys (auto-deploy if enabled)
4. RunPod pulls `tryfitted-avatar-worker:main` for GPU jobs (template uses the same tag)

Workflow file: `.github/workflows/docker-images.yml`

## Recommended domains / ports

- `api.<your-domain>` → API container port `3001`
- `s3.<your-domain>` → MinIO S3 port `9000`
- `minio.<your-domain>` → MinIO console port `9001` (restrict access)
- `redis.<your-domain>` → Redis port `6379` (do not expose publicly unless you must)

## Required environment variables (API)

These map directly to `apps/api` config:

- `DATABASE_URL=postgresql://...`
- `REDIS_URL=redis://:PASSWORD@redis.<your-domain>:6379`
- `S3_ENDPOINT=https://s3.<your-domain>`
- `S3_PUBLIC_BASE_URL=https://s3.<your-domain>` (or use your API proxy if you implement one)
- `S3_ACCESS_KEY=...`
- `S3_SECRET_KEY=...`
- `S3_BUCKET=tryfitted`

Important:
- `S3_ENDPOINT` must be the **public** MinIO address so browser presigned URLs work.

## Notes on exposing Redis + MinIO

The GPU worker must be able to reach Redis (queue) and MinIO (S3) over the network.

Safer options (recommended):
- Put Redis/MinIO on a private network (VPN like Tailscale/WireGuard) and connect RunPod into it.
- Or switch the worker to an API-polling job model (no Redis exposure).

Fastest option for early testing:
- Expose Redis with a strong password and firewall it to only your RunPod pod IP (or a small allowlist).
- Expose MinIO S3 with TLS (`s3.<your-domain>`), keep the console private.

## Model weights (secure + less manual)

Do not commit model weights (SMPL-X / PIXIE / SAM3D / SAM2) to Git.

More automated approach:

- Create a **private** MinIO bucket (recommended: `tryfitted-models`) and upload weights under:
  - `smplx/`
  - `pixie/`
  - `sam3d/`
  - `sam2/checkpoints/`
- Create a MinIO user with **read-only** access to that bucket.
- Configure the RunPod worker with `MODEL_SYNC_*` env vars so it downloads missing weights on startup into its mounted volume.
