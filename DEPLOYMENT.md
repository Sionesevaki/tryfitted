# Deployment (From Zero → Working GPU Pipeline)

This guide gets the full TryFitted pipeline running with:

- **Coolify (VPS)**: API + Postgres + Redis + MinIO (always on, cheap)
- **RunPod (GPU)**: `avatar-worker` container (expensive only when generating avatars)

Repo builds/pushes images to **GHCR** via GitHub Actions, and both Coolify + RunPod pull those images.

## 0) Prerequisites

- A domain you control (recommended)
- A VPS with Coolify installed (or where you’ll install it)
- A RunPod account (GPU pod)
- GitHub repo for this code

## 1) Decide your domains

Recommended:

- `api.<domain>` → API (port `3001` inside container)
- `s3.<domain>` → MinIO S3 (port `9000` inside container)
- `minio.<domain>` → MinIO Console (port `9001` inside container; restrict access)

Redis:

- Best: **do not** expose Redis publicly; use VPN (Tailscale/WireGuard) between RunPod and your VPS.
- Fastest (less safe): expose Redis with a password + firewall allowlist to RunPod IPs.

## 2) Enable CI image builds (GHCR)

This repo includes a workflow that builds and pushes images on every push to `main`:

- `.github/workflows/docker-images.yml`

Images produced:

- `ghcr.io/<owner>/tryfitted-api:main` and `:sha-...`
- `ghcr.io/<owner>/tryfitted-avatar-worker:main` and `:sha-...`

Checklist:

1. Push this repo to GitHub.
2. Ensure Actions are enabled.
3. Run the workflow once (push to `main`) and confirm packages appear in GitHub Packages.

Pull access:

- Easiest: set the packages to **public** while testing.
- Otherwise: create a GitHub token with `read:packages` for Coolify/RunPod to pull images.

## 3) Deploy “core services” on Coolify (VPS)

Use the stack template:

- `infra/coolify/docker-compose.yml`

### 3.1 Create the stack in Coolify

1. In Coolify → **Stacks** → create a new stack.
2. Paste the contents of `infra/coolify/docker-compose.yml`.
3. Add environment variables (below).
4. Configure domains for `api` and `minio` services.

### 3.2 Required Coolify environment variables

Minimum (set these in the stack):

- `GITHUB_REPO_OWNER=<your github org/user>`
- `API_IMAGE_TAG=main`
- `POSTGRES_PASSWORD=<strong>`
- `REDIS_PASSWORD=<strong>`
- `S3_ACCESS_KEY=<strong>`
- `S3_SECRET_KEY=<strong>`
- `S3_BUCKET=tryfitted`

API runtime:

- `DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/tryfitted?schema=public`
- `REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379`
- `S3_ENDPOINT=https://s3.<domain>` (**public MinIO URL**, not `http://minio:9000`)
- `S3_PUBLIC_BASE_URL=https://s3.<domain>`

Why `S3_ENDPOINT` must be public:

- Browser uploads use **presigned MinIO URLs**, so the URL returned by MinIO must be reachable by the user’s browser.

### 3.3 MinIO routing notes

- Route `s3.<domain>` to service `minio` port `9000`.
- Route `minio.<domain>` to service `minio` port `9001` and lock it down (IP allowlist / basic auth / private).

### 3.4 Redis access for RunPod

Choose one:

- **Recommended**: Run a VPN between RunPod and your VPS and use `REDIS_URL=redis://:<pwd>@<vpn-ip>:6379`.
- **Temporary**: expose port `6379` and firewall allowlist RunPod pod IP(s).

## 4) Deploy the GPU worker on RunPod

Worker docs:

- `infra/runpod/README.md`

### 4.1 Create a RunPod template

Container image:

- `ghcr.io/<owner>/tryfitted-avatar-worker:main`

Set environment variables:

- `REDIS_URL=redis://:<REDIS_PASSWORD>@<redis-host>:6379`
- `API_BASE_URL=https://api.<domain>`
- `MINIO_ENDPOINT=s3.<domain>`
- `MINIO_SECURE=true`
- `MINIO_ACCESS_KEY=...`
- `MINIO_SECRET_KEY=...`
- `MINIO_BUCKET=tryfitted`
- `REQUIRE_REAL_AVATAR=true`
- `SMPLX_MODEL_DIR=/app/models/smplx`
- `PIXIE_MODEL_DIR=/app/src/pipeline/PIXIE`

Optional (Option A fit refinement with SAM3D; requires CUDA):

- `SAM3DBODY_ENABLED=true`
- `SAM3DBODY_REPO_DIR=/app/vendors/sam-3d-body`
- `SAM3DBODY_CHECKPOINT_PATH=/app/models/sam3d/model.ckpt`
- `SAM3DBODY_MHR_PATH=/app/models/sam3d/assets/mhr_model.pt`
- `SAM3DBODY_SEGMENTOR_PATH=/app/vendors/sam2`

### 4.2 Mount a RunPod volume for model assets

Do not bake large checkpoints into the image. Mount them as a volume, e.g.:

- `/app/models/smplx/*` (SMPL-X models)
- `/app/src/pipeline/PIXIE/data/*` (PIXIE weights/assets)
- `/app/models/sam3d/*` (SAM3D checkpoint + assets)
- `/app/vendors/sam-3d-body` and `/app/vendors/sam2` (if using Option A)

## 5) Smoke test (end-to-end)

1. Open your web UI (or call the API directly) and request presigned upload URLs:
   - `POST https://api.<domain>/v1/uploads/presign`
2. Upload front+side images to the returned `uploadUrl`.
3. Create an avatar job:
   - `POST https://api.<domain>/v1/avatar/jobs`
4. Confirm the RunPod worker consumes the job (worker logs).
5. Confirm output objects exist in MinIO:
   - `avatars/<jobId>/avatar.glb`
   - `avatars/<jobId>/measurements.json`
   - `avatars/<jobId>/quality_report.json`
   - `avatars/<jobId>/appearance.json`
   - If Option A enabled: `mask_front.png`, `mask_side.png`, `silhouette_targets.json`

## 6) CI/CD operations

- API deploys automatically when Coolify is configured to watch image updates (tag `main`) or when you manually “Redeploy”.
- RunPod worker:
  - For cost control, you can keep the pod off and only start it when testing.
  - When you ship updates, restart the pod to pull the new image tag.

Recommended workflow:

- Use `:sha-...` for production rollouts (immutable) once you’re stable.
- Keep `:main` for fast iteration.

## 7) Common gotchas

- `localhost` in env vars will not work cross-host. RunPod must point at **public/VPN** addresses.
- If MinIO is behind a reverse proxy, ensure large uploads are allowed and CORS is configured.
- If Redis is exposed publicly, use a strong password and firewall allowlists; prefer VPN.

