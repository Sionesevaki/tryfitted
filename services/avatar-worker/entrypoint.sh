#!/usr/bin/env sh
set -eu

log() {
  printf "%s\n" "$*" 1>&2
}

# Optional: sync model assets from a private MinIO bucket into /app/models (mounted volume).
# This avoids manual SCP/rsync into RunPod volumes.
python3 /app/src/model_sync.py || true

# This container bakes code dependencies (PIXIE, SMPL-Anthropometry, optional sam-3d-body/sam2) into the image,
# but large model weights are mounted at runtime under /app/models.
#
# To keep mounts simple (mount just /app/models), copy any provided weights into the locations expected by code.

if [ -d "/app/models/pixie" ]; then
  mkdir -p "/app/src/pipeline/PIXIE/data"
  if [ ! -f "/app/src/pipeline/PIXIE/data/pixie_model.tar" ] && [ -f "/app/models/pixie/pixie_model.tar" ]; then
    log "[entrypoint] Copying PIXIE assets from /app/models/pixie -> /app/src/pipeline/PIXIE/data"
    cp -R "/app/models/pixie/." "/app/src/pipeline/PIXIE/data/" || true
  fi
fi

if [ -d "/app/models/sam2/checkpoints" ] && [ -d "/app/vendors/sam2" ]; then
  mkdir -p "/app/vendors/sam2/checkpoints"
  if [ ! -f "/app/vendors/sam2/checkpoints/sam2.1_hiera_large.pt" ] && [ -f "/app/models/sam2/checkpoints/sam2.1_hiera_large.pt" ]; then
    log "[entrypoint] Copying SAM2 checkpoints from /app/models/sam2/checkpoints -> /app/vendors/sam2/checkpoints"
    cp -R "/app/models/sam2/checkpoints/." "/app/vendors/sam2/checkpoints/" || true
  fi
fi

exec python3 /app/src/worker.py
