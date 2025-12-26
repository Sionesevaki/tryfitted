# TryFitted Avatar Worker

Python-based GPU worker service for processing avatar generation jobs using PIXIE and SMPL-Anthropometry.

## Architecture

This worker consumes jobs from Redis/BullMQ, processes photos using PIXIE to generate SMPL-X body models, extracts measurements using SMPL-Anthropometry, optimizes the GLB output, and uploads results to MinIO.

## Requirements

- Python 3.10+
- NVIDIA GPU with 8GB+ VRAM (RTX 3090 recommended)
- CUDA 11.8+
- Docker (for containerized deployment)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download SMPL-X Models

Register and download SMPL-X model files from https://smpl-x.is.tue.mpg.de/ (free for research).

Place the model files in `models/`:
- `models/smplx/SMPLX_MALE.npz`
- `models/smplx/SMPLX_FEMALE.npz`
- `models/smplx/SMPLX_NEUTRAL.npz`

### 3. Clone PIXIE

PIXIE is vendored in `src/pipeline/PIXIE/`. If you remove it from the repo, re-clone it and follow PIXIE’s install instructions.

### 4. Clone SMPL-Anthropometry

SMPL-Anthropometry is vendored in `src/pipeline/SMPL-Anthropometry/`. If you remove it from the repo, re-clone it.

### 5. Configure Environment

Create `.env` file:
```
REDIS_URL=redis://localhost:6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=tryfitted
API_BASE_URL=http://localhost:3001
```

## Running

### Local Development

```bash
python src/worker.py
```

### Docker

```bash
docker build -t tryfitted-avatar-worker .
docker run --gpus all -e REDIS_URL=redis://host.docker.internal:6379 tryfitted-avatar-worker
```

This Docker image installs `gltfpack` during build, so GLB optimization works in deployment without any host-level install.

### RunPod Deployment

1. Build and push Docker image to registry
2. Create RunPod template with GPU instance
3. Set environment variables
4. Deploy worker

## Pipeline

1. **Download Photos** - Fetch photos from MinIO
2. **PIXIE Processing** - Generate SMPL-X parameters from front photo (and uses side photo if provided to fuse shape)
   - Optional: run SAM 3D Body to generate masks/keypoints and refine SMPL-X shape to match silhouettes (fit accuracy boost)
3. **Measurement Extraction** - Extract 16 body measurements using SMPL-Anthropometry
4. **GLB Export** - Export SMPL-X mesh as GLB file
5. **Optimization** - Run gltfpack to compress GLB (<2MB target)
   - Also tints GLB materials using estimated skin tone from the front photo (best-effort).
6. **Upload** - Upload GLB, measurements, quality report, and appearance metadata to MinIO
7. **Callback** - Update job status via API

## Why the “avatar” looks like a cube/capsule

If PIXIE/SMPL-X can’t load (missing `pixie_model.tar` and required PIXIE data assets, or SMPL-X model path mismatch), the worker intentionally falls back to a placeholder mesh/measurements so you can validate the queue + storage + API plumbing. In that mode you’ll see a simple primitive in the web viewer and the quality report will include a warning about placeholder output.

If you want jobs to fail instead of returning placeholder output, set `REQUIRE_REAL_AVATAR=true` in the worker environment.

## Getting a real avatar (not placeholder)

1) Populate `src/pipeline/PIXIE/data/` with the required PIXIE assets and pretrained weights (at minimum `pixie_model.tar`). This repo currently includes only a few PNGs, which is not enough to run PIXIE.
2) Ensure your SMPL-X model files are available under `models/smplx/` (the worker defaults to `services/avatar-worker/models/smplx` when running from source).
3) Run the worker with `REQUIRE_REAL_AVATAR=true` so you’ll immediately see failures instead of silently producing placeholders.

### Quick local checklist (Windows / running from source)

- `services/avatar-worker/src/pipeline/PIXIE/data/pixie_model.tar` exists (and PIXIE `data/` contains the other referenced assets)
- If you don't have the optional albedo file `FLAME_albedo_from_BFM.npz`, keep `PIXIE_USE_TEX=false` (default) to avoid a startup failure.
- `services/avatar-worker/models/smplx/SMPLX_NEUTRAL.npz` exists (and MALE/FEMALE if desired)
- `services/avatar-worker/src/pipeline/SMPL-Anthropometry/data/smplx/smplx_body_parts_2_faces.json` exists (vendored)
- If SMPL-Anthropometry fails to load with `.npz` models, download the `.pkl` SMPL-X models and set `SMPL_ANTHRO_MODEL_EXT=pkl` (see `.env.example`).
- Install `gltfpack` and set `GLTFPACK_PATH` if it isn’t on your PATH (otherwise the worker will skip optimization and upload an unoptimized GLB).
  - Windows: use forward slashes in `.env` (e.g. `C:/Users/you/tools/gltfpack.exe`) or escape backslashes (`C:\\Users\\you\\tools\\gltfpack.exe`). Avoid quoted values like `"C:\Users\you\tools\gltfpack.exe"` because `\t` becomes a tab and the path breaks.
- If the body looks like the arms are “stuck” to the torso (missing the real-life gap between arm and waist), use a standardized export pose:
  - `AVATAR_DISPLAY_POSE=apose` (default) produces a more natural try-on pose with arms slightly away from the torso.
  - `AVATAR_DISPLAY_POSE=tpose` produces a strict T-pose.
  - `AVATAR_DISPLAY_POSE=pixie` uses the pose predicted from the photo (more “matched”, but can create self-intersections depending on the input).
  - Tune `AVATAR_APOSE_ARM_DOWN_DEG` (e.g. `15`–`35`) if you want arms higher/lower.
- Fit accuracy note: the worker scales the mesh to your provided `heightCm`, so garments and measurements are in the right “real-world” scale.
- Fit accuracy option A (silhouette refinement with SAM 3D Body):
  - Set `SAM3DBODY_ENABLED=true`, `SAM3DBODY_CHECKPOINT_PATH=...`, `SAM3DBODY_MHR_PATH=...`.
  - If you cloned the repo, set `SAM3DBODY_REPO_DIR=...` so the worker can import `tools/*`.
  - Ensure SAM3D dependencies are installed (common missing ones: `roma`, `omegaconf`, `yacs`, `timm`, `einops`, `pytorch-lightning`). Easiest: `pip install -r services/avatar-worker/requirements.txt`.
  - GPU note: SAM 3D Body inference requires CUDA; on CPU-only Torch builds the worker will automatically fall back to GrabCut silhouettes (still enables refinement, but less accurate).
  - Masks:
    - Best: set `SAM3DBODY_SEGMENTOR_PATH` to a SAM2 checkout containing `checkpoints/sam2.1_hiera_large.pt` so SAM3D can generate high-quality masks.
    - Minimal assets: if no segmentor is configured, the worker falls back to bbox-initialized GrabCut masks (works if backgrounds are reasonably clean).
  - For deployment with no runtime downloads, also set `SAM3DBODY_DETECTOR_PATH` and `SAM3DBODY_FOV_PATH` (optional, but recommended).
  - The worker uploads debug artifacts per job: `mask_front.png`, `mask_side.png`, and `silhouette_targets.json` under `avatars/<jobId>/`.

## Performance Targets

- Processing time: <2 minutes per avatar (RTX 3090)
- GLB file size: <2MB
- Triangle count: <10k
- Measurement accuracy: ±2cm variance
