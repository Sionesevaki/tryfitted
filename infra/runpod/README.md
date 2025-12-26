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

Mount a persistent volume to `/app/models` and (optionally) `/app/vendors`:

- `/app/models/smplx/*` (SMPL-X neutral/male/female)
- `/app/models/sam3d/*` (SAM3D checkpoint + assets)
- `/app/src/pipeline/PIXIE/data/*` (PIXIE `pixie_model.tar` + required assets)
- `/app/vendors/sam-3d-body` (repo code)
- `/app/vendors/sam2` (repo code + `checkpoints/*.pt`)

Keeping checkpoints on a volume avoids baking large files into the image and keeps CI/CD fast.

## Cost control tips

- Use RunPod Spot if available (cheaper).
- Keep only the worker on GPU; keep API/DB/Redis/MinIO on the VPS.
- Consider running the worker on-demand (future improvement): replace BullMQ consumption with API polling so the pod can be started only when needed.

