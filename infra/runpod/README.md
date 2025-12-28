# RunPod (GPU) Avatar Worker (production-style)

This runs only the GPU-heavy `services/avatar-worker` on RunPod, while Coolify (VPS) runs the control-plane services (API + Postgres) and provides **Resources** for Redis + MinIO.

## 0) Prereqs (Coolify)

You should already have these reachable from the public internet (or via VPN that the RunPod pod can join):

- API base URL (example): `https://api.tryfitted.com`
- MinIO S3 API URL (example): `https://minioapi.trifitted.com`
- Redis endpoint for the worker to reach (recommended: **VPN/private**; if public, firewall it)

### Redis Resource (Coolify)

- Set a Redis password and keep it stable.
- Prefer a URL-safe password (letters/numbers `-_`), otherwise you must URL-encode it in `REDIS_URL`.
- If you expose Redis publicly: restrict by firewall to RunPod IPs (or use Tailscale/WireGuard instead).

### MinIO Resource (Coolify)

- Configure the resource domains:
  - Console: `https://minio.tryfitted.com`
  - S3 API: `https://minioapi.trifitted.com`
- Create bucket: `tryfitted` (or whatever you set in env)
- Create an access key with read/write permissions to that bucket.

## 1) Container image (GHCR)

Use the CI-built image:

- `ghcr.io/<owner>/tryfitted-avatar-worker:<tag>`

Typical tags:

- `main` (latest from main)
- `sha-<commit>`

CI workflow: `.github/workflows/docker-images.yml`

If your GHCR package is private, add registry credentials in RunPod (GitHub PAT with `read:packages`).

## 2) RunPod template (recommended settings)

1. Create a **RunPod Template**.
2. Container image: `ghcr.io/<owner>/tryfitted-avatar-worker:<tag>`
3. GPU: any CUDA-capable GPU works; start with 16GB+ VRAM if you enable SAM3D refinement.
4. Mount a **Network Volume** at: `/app/models`

Why `/app/models`?
- The image already includes code (PIXIE, SMPL-Anthropometry, optional SAM3D + SAM2).
- You only need to provide weights/assets, and you want them persistent across redeploys.

Recommended volume sizing:
- Set a **Network Volume size > 0** (example: 50–200GB). If you leave it at `0`, you have nowhere persistent to store model assets.

## 3) Worker environment variables (RunPod)

### Copy/paste env template (minimal)

Paste this into RunPod’s Environment (replace placeholders):

```bash
# Core connectivity
API_BASE_URL=https://api.tryfitted.com
REDIS_URL=redis://:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:6379

# MinIO (S3 API domain from your Coolify MinIO Resource)
MINIO_ENDPOINT=minioapi.trifitted.com
MINIO_SECURE=true
MINIO_ACCESS_KEY=YOUR_MINIO_ACCESS_KEY
MINIO_SECRET_KEY=YOUR_MINIO_SECRET_KEY
MINIO_BUCKET=tryfitted

# Safety: fail fast instead of placeholder output / skipped optimization
REQUIRE_REAL_AVATAR=true
REQUIRE_GLTFPACK=true
```

Notes:
- `MINIO_ENDPOINT` is `host[:port]` only (no `https://`). Use `MINIO_SECURE=true` for HTTPS.
- `REDIS_URL` must be a full URL. If the Redis password contains special characters (like `/` or `=`), URL-encode it or rotate the password to URL-safe characters.
  - Use port `6379` for `redis://` (no TLS). Only use `6380` with `rediss://` if you have actually enabled TLS on Redis.

### Core (required)

- `API_BASE_URL=https://api.tryfitted.com`
- `REDIS_URL=redis://:YOUR_PASSWORD@<redis-host>:6379`
- `MINIO_ENDPOINT=minioapi.trifitted.com`
- `MINIO_SECURE=true`
- `MINIO_ACCESS_KEY=...`
- `MINIO_SECRET_KEY=...`
- `MINIO_BUCKET=tryfitted`
- `REQUIRE_REAL_AVATAR=true`
- `REQUIRE_GLTFPACK=true`

Important:
- `MINIO_ENDPOINT` must be `host[:port]` (no `http://` / `https://`). `MINIO_SECURE=true` enables HTTPS.
- If your Redis password contains `/`, `@`, `:` or `=`, URL-encode it, e.g. `/` → `%2F`, `=` → `%3D`.
  - If you keep hitting auth issues, rotate the Redis password to URL-safe characters instead.

### Model paths (usually leave defaults)

Defaults in the image already point where you want:

- `SMPLX_MODEL_DIR=/app/models/smplx`
- `PIXIE_MODEL_DIR=/app/src/pipeline/PIXIE`
- `GLTFPACK_PATH=gltfpack`

You typically do **not** need to set these unless you have a custom layout.

### Fit accuracy “Option A” (optional, requires GPU)

Enable silhouette refinement via SAM 3D Body:

- `SAM3DBODY_ENABLED=true`
- `SAM3DBODY_REPO_DIR=/app/vendors/sam-3d-body` (included in image)
- `SAM3DBODY_CHECKPOINT_PATH=/app/models/sam3d/model.ckpt`
- `SAM3DBODY_MHR_PATH=/app/models/sam3d/assets/mhr_model.pt`
- `SAM3DBODY_SEGMENTOR_PATH=/app/vendors/sam2` (included in image)

### Copy/paste env template (Option A + model sync)

If you want maximum fit accuracy + no manual copying into the RunPod volume, use this (still replace placeholders):

```bash
# --- Core (same as minimal) ---
API_BASE_URL=https://api.tryfitted.com
REDIS_URL=redis://:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:6379
MINIO_ENDPOINT=minioapi.trifitted.com
MINIO_SECURE=true
MINIO_ACCESS_KEY=YOUR_MINIO_ACCESS_KEY
MINIO_SECRET_KEY=YOUR_MINIO_SECRET_KEY
MINIO_BUCKET=tryfitted
REQUIRE_REAL_AVATAR=true
REQUIRE_GLTFPACK=true

# --- Fit accuracy (Option A) ---
SAM3DBODY_ENABLED=true
SAM3DBODY_REPO_DIR=/app/vendors/sam-3d-body
SAM3DBODY_CHECKPOINT_PATH=/app/models/sam3d/model.ckpt
SAM3DBODY_MHR_PATH=/app/models/sam3d/assets/mhr_model.pt
SAM3DBODY_SEGMENTOR_PATH=/app/vendors/sam2

# --- Auto-sync models from a PRIVATE MinIO bucket (recommended) ---
MODEL_SYNC_ENABLED=true
MODEL_SYNC_MINIO_ENDPOINT=minioapi.trifitted.com
MODEL_SYNC_MINIO_SECURE=true
# Your private models bucket name (example shown)
MODEL_SYNC_MINIO_BUCKET=trifitted-models
MODEL_SYNC_MINIO_ACCESS_KEY=YOUR_MODELS_BUCKET_ACCESS_KEY
MODEL_SYNC_MINIO_SECRET_KEY=YOUR_MODELS_BUCKET_SECRET_KEY
MODEL_SYNC_PREFIX=
MODEL_SYNC_SOURCES=smplx,pixie,sam3d,sam2,tools
MODEL_SYNC_LOCAL_ROOT=/app/models
```

## 4) What to put on the RunPod volume (`/app/models`)

There are two ways to provide model assets:

1) **Recommended (production)**: put everything in a **private MinIO bucket** and enable `MODEL_SYNC_ENABLED=true` (the worker downloads assets at startup).
2) **Manual**: upload/copy files into the RunPod Network Volume mounted at `/app/models`.

### Manual mode: minimum required to generate a real avatar

- `smplx/`
  - `SMPLX_NEUTRAL.npz` (and optional `SMPLX_MALE.npz`, `SMPLX_FEMALE.npz`)
- `pixie/`
  - `pixie_model.tar` (+ any other PIXIE `data/` assets you downloaded)

Optional (only if you enable SAM3D refinement):

- `sam3d/`
  - `model.ckpt`
  - `assets/mhr_model.pt`
- `sam2/checkpoints/`
  - `sam2.1_hiera_large.pt` (or whichever checkpoint you configured)

Optional (only if you want to provide your own gltfpack binary):

- `tools/`
  - `gltfpack` (Linux binary) or `gltfpack/gltfpack`

The container entrypoint will copy:
- `/app/models/pixie/*` → `/app/src/pipeline/PIXIE/data/` (if `pixie_model.tar` is missing there)
- `/app/models/sam2/checkpoints/*` → `/app/vendors/sam2/checkpoints/` (if missing)
- `/app/models/tools/gltfpack*` → `/usr/local/bin/gltfpack` (if not already installed)

## 5) Recommended: auto-sync model files from MinIO (no SCP/rsync)

If you don’t want to manually copy files into the RunPod Network Volume, the worker can download missing assets at startup from a **private MinIO bucket**.

This is the best long-term approach because:
- Your RunPod pods can be recreated at any time and still self-heal.
- You don’t need to SSH/SCP into RunPod or manage volumes manually.
- You can rotate keys and control access via MinIO policies.

### 5.1 Create the private MinIO bucket

1. In MinIO Console, create a bucket (example): `trifitted-models`
2. Keep it **private** (no public bucket policy).
3. Create a MinIO user (or access key) with **read-only** access to this bucket.

Suggested minimal policy (read-only):
- `s3:GetObject` on `trifitted-models/*`
- `s3:ListBucket` on `trifitted-models`

Important:
- This bucket is for **model assets only** (SMPL-X / PIXIE / SAM3D / SAM2). Do not mix it with your public `tryfitted` bucket that stores user uploads + generated avatars.
- With `MODEL_SYNC_ENABLED=true`, the worker will **fail fast** at startup if sync is misconfigured or can’t reach the bucket (this is intentional so you don’t silently fall back to placeholders).

### 5.2 Bucket layout (exact folder structure)

Upload your model files to the `trifitted-models` bucket with this layout:

- `smplx/`
  - `SMPLX_NEUTRAL.npz`
  - (optional) `SMPLX_MALE.npz`
  - (optional) `SMPLX_FEMALE.npz`
- `pixie/`
  - `pixie_model.tar`
  - (optional) any additional PIXIE assets you downloaded
- `sam3d/` (only if using silhouette refinement)
  - `model.ckpt`
  - `assets/mhr_model.pt`
- `sam2/` (only if using silhouette refinement)
  - `checkpoints/`
    - `sam2.1_hiera_large.pt` (or whichever SAM2 checkpoint you choose)
- `tools/` (optional)
  - `gltfpack` (Linux binary) or `gltfpack-linux` renamed to `gltfpack`

At startup, model sync downloads into `MODEL_SYNC_LOCAL_ROOT` (default `/app/models`), and then the entrypoint copies/links into the paths the code expects.

### 5.2.1 Uploading into the bucket (quickest way)

If you already downloaded the assets locally, the simplest approach is:

1. Install MinIO Client (`mc`) locally (or use it inside a trusted admin VM).
2. Point it at your MinIO S3 API domain (example uses HTTPS):

```bash
mc alias set models https://minioapi.trifitted.com YOUR_MINIO_ADMIN_ACCESS_KEY YOUR_MINIO_ADMIN_SECRET_KEY
mc mb -p models/trifitted-models
```

3. Upload folders (examples assume you already have the files on disk):

```bash
# SMPL-X files (copy the folder containing SMPLX_*.[npz|pkl])
mc cp --recursive /path/to/smplx models/trifitted-models/smplx

# PIXIE assets: copy EVERYTHING from PIXIE/data (recommended)
mc cp --recursive /path/to/PIXIE/data models/trifitted-models/pixie

# SAM3D checkpoint + assets
mc cp /path/to/model.ckpt models/trifitted-models/sam3d/model.ckpt
mc cp /path/to/mhr_model.pt models/trifitted-models/sam3d/assets/mhr_model.pt

# SAM2 checkpoint(s)
mc cp --recursive /path/to/sam2/checkpoints models/trifitted-models/sam2/checkpoints
```

Tip: for PIXIE, the safest “it just works” approach is to upload the entire `PIXIE/data/` directory contents, not only `pixie_model.tar`.

Alternatively, this repo includes an uploader script you can run from your machine:

- Bash script (macOS/Linux/WSL/Git Bash): `infra/runpod/upload_models_to_minio.sh`
- PowerShell script (Windows): `infra/runpod/upload_models_to_minio.ps1`
- Python script (no `mc`): `infra/runpod/upload_models_to_minio.py`
- It uploads `smplx/`, `pixie/`, `sam3d/`, `sam2/checkpoints/`, and optional `tools/gltfpack` to your private models bucket.

#### Windows PowerShell example (recommended on Windows)

In PowerShell, don’t use `export`/`chmod` (those are Bash commands). Set env vars like this and run the `.ps1` script:

```powershell
# S3 API URL (NOT the MinIO console URL)
$env:MINIO_URL="https://minioapi.trifitted.com"
$env:MINIO_ACCESS_KEY="YOUR_ACCESS_KEY"
$env:MINIO_SECRET_KEY="YOUR_SECRET_KEY"
$env:MODELS_BUCKET="trifitted-models"

# Local sources to upload (repo-relative paths are OK)
$env:SMPLX_DIR="services/avatar-worker/models/smplx"
$env:PIXIE_DATA_DIR="services/avatar-worker/src/pipeline/PIXIE/data"
$env:SAM3D_CHECKPOINT="vendors/sam-3d-body-vith/model.ckpt"
$env:SAM3D_MHR_MODEL="vendors/sam-3d-body-vith/assets/mhr_model.pt"
$env:SAM2_CHECKPOINTS_DIR="vendors/sam2/checkpoints"
$env:GLTFPACK_FILE="vendors/tools/gltfpack"

# Dry run
$env:DRY_RUN="true"
powershell -ExecutionPolicy Bypass -File infra/runpod/upload_models_to_minio.ps1

# Real upload
$env:DRY_RUN="false"
powershell -ExecutionPolicy Bypass -File infra/runpod/upload_models_to_minio.ps1
```

#### Simplest option: Python uploader (no `mc` required)

If you don’t want to install `mc`, use the Python uploader:

1) Install dependency:

```powershell
python -m pip install minio
```

2) Run (PowerShell example):

```powershell
$env:MINIO_URL="https://minioapi.trifitted.com"   # S3 API URL, not console
$env:MINIO_ACCESS_KEY="YOUR_ACCESS_KEY"
$env:MINIO_SECRET_KEY="YOUR_SECRET_KEY"
$env:MODELS_BUCKET="trifitted-models"

$env:SMPLX_DIR="services/avatar-worker/models/smplx"
$env:PIXIE_DATA_DIR="services/avatar-worker/src/pipeline/PIXIE/data"
$env:SAM3D_CHECKPOINT="vendors/sam-3d-body-vith/model.ckpt"
$env:SAM3D_MHR_MODEL="vendors/sam-3d-body-vith/assets/mhr_model.pt"
$env:SAM2_CHECKPOINTS_DIR="vendors/sam2/checkpoints"
$env:GLTFPACK_FILE="vendors/tools/gltfpack"

# Optional (only if your TLS cert isn't trusted):
# $env:MINIO_INSECURE="true"

# Dry run
$env:DRY_RUN="true"
python infra/runpod/upload_models_to_minio.py

# Real upload
$env:DRY_RUN="false"
python infra/runpod/upload_models_to_minio.py
```

### 5.3 Where to get the files (what you’re actually adding)

This project needs 4 categories of “big files” that you do NOT commit to Git:

#### A) SMPL-X body model files (`smplx/…`)

Purpose: the actual human body mesh/shape space. Without this you’ll get placeholder meshes or failures.

What to upload:
- `SMPLX_NEUTRAL.npz` (required)
- `SMPLX_MALE.npz`, `SMPLX_FEMALE.npz` (optional)

Where to get it:
- Download from the official **SMPL-X** model distribution after accepting the license (this is usually via the SMPL-X/Max Planck Body Labs site).

#### B) PIXIE weights/assets (`pixie/…`)

Purpose: estimate SMPL-X parameters from your uploaded photos.

What to upload:
- `pixie_model.tar` (required)
- Recommended: upload the entire contents of `PIXIE/data/` (the PIXIE repo requires more than just `pixie_model.tar` for some modes).
- If you plan to enable textures (`PIXIE_USE_TEX=true`), you will also need the extra FLAME/texture assets referenced by PIXIE.

Where to get it:
- Follow the PIXIE repo instructions (the worker expects the `pixie_model.tar` weight file in `PIXIE/data`).
- If you already downloaded PIXIE files locally, just copy those into the bucket under `pixie/`.

#### C) SAM 3D Body + MHR assets (`sam3d/…`) (Option A only)

Purpose: silhouette/mask-driven refinement to improve **fit accuracy** (better alignment between the avatar silhouette and the input images).

What to upload:
- `sam3d/model.ckpt`
- `sam3d/assets/mhr_model.pt`

Where to get it:
- From the `facebookresearch/sam-3d-body` project’s official checkpoints/assets (you already mentioned you have access).

#### D) SAM2 checkpoint (`sam2/checkpoints/…`) (Option A only)

Purpose: segmentation/masks used by SAM 3D Body for refinement.

What to upload:
- One SAM2 checkpoint file, e.g. `sam2.1_hiera_large.pt`

Where to get it:
- From the official **SAM2** checkpoint downloads (Meta/Facebook Research provides them; you already cloned `facebookresearch/sam2`).

#### Optional: gltfpack (`tools/…`)

Purpose: optimize GLB size/performance.

Notes:
- The Docker image installs `gltfpack` already; you usually do not need to upload this.
- Only upload it if you want to control the binary version yourself.

### 5.4 RunPod env vars for model sync

In RunPod env, set:
   - `MODEL_SYNC_ENABLED=true`
   - `MODEL_SYNC_MINIO_ENDPOINT=minioapi.trifitted.com`
   - `MODEL_SYNC_MINIO_SECURE=true`
   - `MODEL_SYNC_MINIO_BUCKET=trifitted-models`
   - `MODEL_SYNC_MINIO_ACCESS_KEY=...`
   - `MODEL_SYNC_MINIO_SECRET_KEY=...`
   - `MODEL_SYNC_SOURCES=smplx,pixie,sam3d,sam2,tools`
   - `MODEL_SYNC_LOCAL_ROOT=/app/models`

Notes:
- Sync is “missing-files only” (won’t re-download if same size exists).
- Model sync runs at container start, before the worker begins consuming jobs.

## 6) What you should see when it’s working

RunPod logs should show (roughly):

- “Starting Avatar Worker…”
- “Initialized MinIO client: …”
- “Successfully connected to Redis”
- “Worker ready and listening for jobs…”

Trigger an avatar build from your UI/API and you should see:

- “Processing job …”
- PIXIE running (no placeholder warnings)
- “Optimizing GLB…” and a gltfpack output
- Uploads to MinIO under `avatars/<jobId>/…`

## 7) Troubleshooting

### `Name or service not known` (DNS) on RunPod

This means the hostname in your env vars does not resolve from RunPod.

- **Redis:** if you used a Coolify Resource URL like `...@zcsw0goksc0...:6380`, that hostname is **internal to Coolify** and will NOT resolve from RunPod.
  - Use a **public IP/domain** (firewalled) like `redis://:<pass>@redis.tryfitted.com:6379`, or connect RunPod ↔ VPS via VPN (Tailscale/WireGuard) and use the private IP.
- **MinIO:** ensure your S3 API domain (example `minioapi.trifitted.com`) has public DNS records (A/CNAME) and points at your VPS proxy.
  - Watch for typos like `trifitted.com` vs `tryfitted.com`.

### Redis auth errors (`NOAUTH` / `WRONGPASS`)

- Ensure the worker `REDIS_URL` points to the same Redis instance the API uses.
- If Redis is a Coolify Resource, prefer copying the resource’s own connection URL rather than hand-building one.
- If your password has special characters, rotate it to URL-safe chars or URL-encode it in `REDIS_URL`.

### MinIO connection works but URLs are wrong

- Ensure `MINIO_ENDPOINT` is your public S3 domain (example `minioapi.trifitted.com`) so generated `http(s)://…/bucket/object` URLs are correct.
- Ensure `MINIO_SECURE=true` if you’re using `https://`.

### MinIO uploads work but the web viewer gets 403/AccessDenied

- The current app expects avatar artifacts to be publicly readable (at least `avatars/*`) so the browser can load `.../avatars/<jobId>/avatar.glb`.
- In MinIO, set a bucket policy to allow `s3:GetObject` on the `tryfitted` bucket (or `avatars/*` prefix), or give the worker credentials permission to call `SetBucketPolicy` (it tries to set public-read on startup).

### Avatar is a cube / placeholder

- PIXIE or SMPL-X assets are missing. Confirm:
  - `/app/models/smplx/SMPLX_NEUTRAL.npz` exists
  - `/app/models/pixie/pixie_model.tar` exists
- Keep `REQUIRE_REAL_AVATAR=true` so jobs fail loudly instead of silently producing placeholders.

### Silhouette refinement is skipped

- You need GPU + the required SAM3D/SAM2 checkpoints.
- Confirm `SAM3DBODY_ENABLED=true` and the paths under `/app/models/sam3d` and `/app/models/sam2/checkpoints`.

## 8) Security notes (important)

- Do not leave Redis publicly exposed without a strong password + firewall.
- Prefer a VPN (Tailscale/WireGuard) between RunPod and your VPS for Redis/MinIO/API.
