# RunPod (GPU) Worker Deployment

Goal: run only the GPU-heavy `avatar-worker` on RunPod, while Coolify (VPS) hosts API + Redis + MinIO (+ Postgres).

## Container image

Use the image built by CI:

- `ghcr.io/<owner>/tryfitted-avatar-worker:main`

Workflow: `.github/workflows/docker-images.yml`

## What the worker needs to reach

From the RunPod pod, the container must be able to reach:

- Redis (BullMQ queue): `REDIS_URL=redis://:PASSWORD@redis.<your-domain>:6379`
- API: `API_BASE_URL=https://api.<your-domain>`
- MinIO S3: `MINIO_ENDPOINT=s3.<your-domain>` and `MINIO_SECURE=true`

## Required environment variables (worker)

Core:

- `REDIS_URL=redis://:PASSWORD@redis.<your-domain>:6379`
- `API_BASE_URL=https://api.<your-domain>`
- `MINIO_ENDPOINT=s3.<your-domain>`
- `MINIO_SECURE=true`
- `MINIO_ACCESS_KEY=...`
- `MINIO_SECRET_KEY=...`
- `MINIO_BUCKET=tryfitted`
- `REQUIRE_REAL_AVATAR=true`

Model paths (these should point at your mounted volume):

- `SMPLX_MODEL_DIR=/app/models/smplx`
- `PIXIE_MODEL_DIR=/app/src/pipeline/PIXIE`

Optional: fit-accuracy Option A (silhouette refinement)

- `SAM3DBODY_ENABLED=true`
- `SAM3DBODY_REPO_DIR=/app/vendors/sam-3d-body`
- `SAM3DBODY_CHECKPOINT_PATH=/app/models/sam3d/model.ckpt`
- `SAM3DBODY_MHR_PATH=/app/models/sam3d/assets/mhr_model.pt`
- `SAM3DBODY_SEGMENTOR_PATH=/app/vendors/sam2`

Notes:
- SAM 3D Body inference requires CUDA. RunPod is the right place to enable this.

## What to mount on the pod (Network Volume)

Mount a persistent volume to `/app/models`.

The worker image includes the required code repos (PIXIE, SMPL-Anthropometry, sam-3d-body, sam2). You only mount weights/assets.

- `/app/models/smplx/*` (SMPL-X neutral/male/female)
- `/app/models/sam3d/*` (SAM3D checkpoint + assets)
- `/app/models/pixie/*` (PIXIE `pixie_model.tar` + required assets; copied into the right place at startup)
- `/app/models/sam2/checkpoints/*` (SAM2 checkpoints; copied into `/app/vendors/sam2/checkpoints` at startup)

Keeping checkpoints on a volume avoids baking large files into the image and keeps CI/CD fast.

## Easier + secure: auto-sync weights from MinIO

Instead of SSH/SCP into the volume, you can upload model files once to a **private** MinIO bucket (e.g. `tryfitted-models`) and let the worker download missing files at startup.

1. In MinIO, create bucket: `tryfitted-models` (keep it private)
2. Upload files into these prefixes:
   - `smplx/`
   - `pixie/`
   - `sam3d/`
   - `sam2/checkpoints/`
3. Create a MinIO user with a **read-only** policy limited to that bucket/prefix.
4. Enable model sync on the worker (RunPod env):
   - `MODEL_SYNC_ENABLED=true`
   - `MODEL_SYNC_MINIO_ENDPOINT=s3.tryfitted.com`
   - `MODEL_SYNC_MINIO_SECURE=true`
   - `MODEL_SYNC_MINIO_BUCKET=tryfitted-models`
   - `MODEL_SYNC_MINIO_ACCESS_KEY=...`
   - `MODEL_SYNC_MINIO_SECRET_KEY=...`

### Suggested volume folder layout

Create these folders inside the volume:

- `/app/models/smplx/` (put `SMPLX_NEUTRAL.*` / `SMPLX_MALE.*` / `SMPLX_FEMALE.*` here)
- `/app/models/sam3d/`
  - `model.ckpt`
  - `assets/mhr_model.pt`

For PIXIE assets, choose one approach:

- **Bind-mount** `/app/models/pixie` → `/app/src/pipeline/PIXIE/data` (recommended), or
- Copy PIXIE assets directly into `/app/src/pipeline/PIXIE/data` on the volume.

### One-time “populate the volume” workflow

1. Create a **Network Volume** in RunPod.
2. Start a temporary small pod (CPU is fine) that mounts the volume at `/app`.
3. SSH into that pod and `scp`/`rsync` your local model files into the mounted paths.
4. Stop/delete the temporary pod; reuse the same volume for the GPU worker pod.

## Cost control tips

- Use RunPod Spot if available (cheaper).
- Keep only the worker on GPU; keep API/DB/Redis/MinIO on the VPS.
- Consider running the worker on-demand (future improvement): replace BullMQ consumption with API polling so the pod can be started only when needed.
