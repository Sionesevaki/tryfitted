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

The workflow only rebuilds images whose code changed (API vs worker), to keep CI fast.

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

Choose one approach:

### Option A: Everything in one stack (simplest)

- `infra/coolify/docker-compose.yml`

This runs **Postgres + Redis + MinIO + API** all inside the stack.

### Option B: Use Coolify “Resources” for MinIO/Redis (recommended on Coolify)

- `infra/coolify/docker-compose.resources.yml`

This runs **Postgres + API** in the stack, and you run **MinIO** (and optionally **Redis**) as Coolify Resources with their own domains.

### 3.1 Create the stack in Coolify

1. In Coolify → **Stacks** → create a new stack.
2. Paste the contents of either `infra/coolify/docker-compose.yml` (Option A) or `infra/coolify/docker-compose.resources.yml` (Option B).
3. Add environment variables (below).
4. Configure the domain for the `api` service (Option A or B).

Notes:

- Do **not** attach domains to `minio-init` (it’s a one-shot container).
- If you’re using MinIO as a **Coolify Resource**, you attach domains on the **Resource** (e.g. `minio.<domain>` and `s3.<domain>`), not in the stack.

### 3.2 Required Coolify environment variables

Minimum (set these in the stack; Option A or B):

- `GITHUB_REPO_OWNER=<your github org/user>`
- `API_IMAGE_TAG=main`
- `POSTGRES_PASSWORD=<strong>`
- `S3_BUCKET=tryfitted`

API runtime:

- `DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/tryfitted?schema=public`
- `S3_ENDPOINT=https://s3.<domain>` (**public MinIO URL**, not `http://minio:9000`)
- `S3_PUBLIC_BASE_URL=https://s3.<domain>`
- `S3_ACCESS_KEY=<minio access key>`
- `S3_SECRET_KEY=<minio secret key>`
- `REDIS_URL=redis://:<redis password>@<redis host>:6379`

Why `S3_ENDPOINT` must be public:

- Browser uploads use **presigned MinIO URLs**, so the URL returned by MinIO must be reachable by the user’s browser.

Option A extras (stack-managed Redis/MinIO):

- `REDIS_PASSWORD=<strong>`
- `REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379`
- `S3_ACCESS_KEY=<strong>`
- `S3_SECRET_KEY=<strong>`

Option B extras (Coolify Resources):

- Set `REDIS_URL` to your Redis Resource endpoint (prefer private networking/VPN).
- Set `S3_ENDPOINT`, `S3_PUBLIC_BASE_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` to the MinIO Resource values.

### 3.3 MinIO routing notes

Option A (MinIO in stack):

- Route `s3.<domain>` to service `minio` port `9000`.
- Route `minio.<domain>` to service `minio` port `9001` and lock it down (IP allowlist / basic auth / private).

Option B (MinIO Resource):

- Configure these directly in the MinIO Resource UI:
  - Console URL → `https://minio.<domain>`
  - S3 API URL → `https://s3.<domain>`

### 3.4 Model weights bucket (recommended)

To keep RunPod setup automated and secure, store model weights in **private MinIO** on the same VPS:

1. Create bucket: `tryfitted-models` (private)
2. Upload weights into prefixes:
   - `smplx/` (SMPL-X model files)
   - `pixie/` (PIXIE `pixie_model.tar` + other required `data/` assets)
   - `sam3d/` (SAM3D `model.ckpt` and `assets/mhr_model.pt`)
   - `sam2/checkpoints/` (SAM2 checkpoint files)
   - `tools/` (optional helper binaries, e.g. `tools/gltfpack` for Linux)
3. Create a MinIO user with **read-only** access to `tryfitted-models/*` (this is what RunPod uses for sync).

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
- `REQUIRE_GLTFPACK=true`
- `SMPLX_MODEL_DIR=/app/models/smplx`
- `PIXIE_MODEL_DIR=/app/src/pipeline/PIXIE`

Optional (Option A fit refinement with SAM3D; requires CUDA):

- `SAM3DBODY_ENABLED=true`
- `SAM3DBODY_REPO_DIR=/app/vendors/sam-3d-body`
- `SAM3DBODY_CHECKPOINT_PATH=/app/models/sam3d/model.ckpt`
- `SAM3DBODY_MHR_PATH=/app/models/sam3d/assets/mhr_model.pt`
- `SAM3DBODY_DETECTOR_PATH=/app/vendors/sam-3d-body`
- `SAM3DBODY_SEGMENTOR_PATH=/app/vendors/sam2`
- `SAM3DBODY_FOV_PATH=/app/vendors/sam-3d-body`

### 4.2 Mount a RunPod volume for model assets

Do not bake large checkpoints into the image. Mount a RunPod **Network Volume** to:

- `/app/models`

Preferred (less manual + secure):

- Upload model files once to the **private** MinIO bucket `tryfitted-models` (Step 3.4)
- In RunPod env, enable auto-sync:
  - `MODEL_SYNC_ENABLED=true`
  - `MODEL_SYNC_MINIO_ENDPOINT=s3.<domain>`
  - `MODEL_SYNC_MINIO_SECURE=true`
  - `MODEL_SYNC_MINIO_BUCKET=tryfitted-models`
  - `MODEL_SYNC_MINIO_ACCESS_KEY=...` (read-only key)
  - `MODEL_SYNC_MINIO_SECRET_KEY=...`
  - `MODEL_SYNC_SOURCES=smplx,pixie,sam3d,sam2`
  - Optional: add `tools` and upload a Linux `gltfpack` binary at `tools/gltfpack` to enable GLB optimization without downloading during image build
  - `MODEL_SYNC_LOCAL_ROOT=/app/models`

Manual fallback (only if you don’t want sync):

- Copy files into the volume paths:
  - `/app/models/smplx/*`
  - `/app/models/pixie/*`
  - `/app/models/sam3d/*`
  - `/app/models/sam2/checkpoints/*`

## 5) Smoke test (end-to-end)

### 5.1 Local UI (recommended while testing deployment)

For now, you can run the UI locally while the backend is deployed to `api.<domain>` and `s3.<domain>`.

In this repo, `apps/web` uses the Vite dev proxy. Set these env vars when starting the dev server:

- `VITE_API_ORIGIN=https://api.<domain>`
- `VITE_MINIO_ORIGIN=https://s3.<domain>`

Example:

- `VITE_API_ORIGIN=https://api.tryfitted.com VITE_MINIO_ORIGIN=https://s3.tryfitted.com pnpm --filter @tryfitted/web dev`

### 5.2 End-to-end

1. From the UI (or call the API directly) request presigned upload URLs:
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
- If GitHub Actions fails with `ERR_PNPM_OUTDATED_LOCKFILE`, run `pnpm install` locally to regenerate `pnpm-lock.yaml` and commit it.
- If the avatar GLB is meshopt-compressed, the viewer must set `GLTFLoader.setMeshoptDecoder(...)` before loading.
