#!/usr/bin/env sh
set -eu

log() {
  printf "%s\n" "$*" 1>&2
}

# Minimal env bool helper
is_true() {
  value="${1:-}"
  case "$(printf "%s" "$value" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

# Optional: sync model assets from a private MinIO bucket into /app/models (mounted volume).
# This avoids manual SCP/rsync into RunPod volumes.
if is_true "${MODEL_SYNC_ENABLED:-false}"; then
  log "[entrypoint] MODEL_SYNC_ENABLED=true; syncing model assets..."
  python3 /app/src/model_sync.py
else
  python3 /app/src/model_sync.py || true
fi

# This container bakes code dependencies (PIXIE, SMPL-Anthropometry, optional sam-3d-body/sam2) into the image,
# but large model weights are mounted at runtime under /app/models.
#
# To keep mounts simple (mount just /app/models), copy any provided weights into the locations expected by code.

# Optional: install gltfpack from the mounted model/tools volume (avoids relying on GitHub release downloads).
# Expected locations (Linux binary):
# - /app/models/tools/gltfpack
# - /app/models/tools/gltfpack/gltfpack
if [ ! -x "/usr/local/bin/gltfpack" ]; then
  if [ -f "/app/models/tools/gltfpack" ]; then
    log "[entrypoint] Installing gltfpack from /app/models/tools/gltfpack -> /usr/local/bin/gltfpack"
    cp "/app/models/tools/gltfpack" "/usr/local/bin/gltfpack" || true
    chmod +x "/usr/local/bin/gltfpack" || true
  elif [ -f "/app/models/tools/gltfpack/gltfpack" ]; then
    log "[entrypoint] Installing gltfpack from /app/models/tools/gltfpack/gltfpack -> /usr/local/bin/gltfpack"
    cp "/app/models/tools/gltfpack/gltfpack" "/usr/local/bin/gltfpack" || true
    chmod +x "/usr/local/bin/gltfpack" || true
  fi
fi

if is_true "${REQUIRE_GLTFPACK:-false}"; then
  if ! command -v gltfpack >/dev/null 2>&1; then
    log "[entrypoint] ERROR: REQUIRE_GLTFPACK=true but gltfpack is not installed."
    log "[entrypoint] Fix: bake gltfpack into the image OR sync a Linux binary to /app/models/tools/gltfpack."
    exit 1
  fi
fi

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
