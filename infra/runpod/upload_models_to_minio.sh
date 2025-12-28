#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "ERROR: $*" 1>&2
  exit 1
}

note() {
  echo "[upload-models] $*" 1>&2
}

need() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "${value}" ]]; then
    die "Missing required env var: ${name}"
  fi
}

file_exists() {
  local p="$1"
  [[ -f "$p" ]] || die "File not found: $p"
}

dir_exists() {
  local p="$1"
  [[ -d "$p" ]] || die "Directory not found: $p"
}

DRY_RUN="${DRY_RUN:-false}"
if [[ "${DRY_RUN}" == "1" || "${DRY_RUN,,}" == "true" ]]; then
  DRY_RUN="true"
else
  DRY_RUN="false"
fi

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    note "DRY_RUN: $*"
    return 0
  fi
  "$@"
}

if ! command -v mc >/dev/null 2>&1; then
  cat 1>&2 <<'EOF'
ERROR: 'mc' (MinIO Client) is not installed.

Install it from: https://min.io/docs/minio/linux/reference/minio-mc.html

Quick sanity check:
  mc --version
EOF
  exit 1
fi

need MINIO_URL
need MINIO_ACCESS_KEY
need MINIO_SECRET_KEY

MINIO_ALIAS="${MINIO_ALIAS:-models}"
MODELS_BUCKET="${MODELS_BUCKET:-trifitted-models}"
MODELS_PREFIX="${MODELS_PREFIX:-}"
MINIO_INSECURE="${MINIO_INSECURE:-false}"

MC_EXTRA_ARGS=()
if [[ "${MINIO_INSECURE}" == "1" || "${MINIO_INSECURE,,}" == "true" ]]; then
  MC_EXTRA_ARGS+=(--insecure)
fi

remote_root="${MODELS_PREFIX#/}"
remote_root="${remote_root%/}"

if [[ -n "${remote_root}" ]]; then
  remote_root="${remote_root}/"
fi

note "Config:"
note "  MINIO_URL=${MINIO_URL}"
note "  MINIO_ALIAS=${MINIO_ALIAS}"
note "  MODELS_BUCKET=${MODELS_BUCKET}"
note "  MODELS_PREFIX=${MODELS_PREFIX:-<empty>}"
note "  MINIO_INSECURE=${MINIO_INSECURE}"

# Optional inputs (set the ones you have):
# - SMPLX_DIR: directory containing SMPL-X model files (e.g. SMPLX_NEUTRAL.npz / .pkl)
# - PIXIE_DATA_DIR: directory containing PIXIE/data assets (recommended: upload whole folder contents)
# - SAM3D_CHECKPOINT: path to model.ckpt
# - SAM3D_MHR_MODEL: path to mhr_model.pt
# - SAM2_CHECKPOINTS_DIR: directory containing SAM2 checkpoint(s) (e.g. sam2.1_hiera_large.pt)
# - GLTFPACK_FILE: path to Linux gltfpack binary

SMPLX_DIR="${SMPLX_DIR:-}"
PIXIE_DATA_DIR="${PIXIE_DATA_DIR:-}"
SAM3D_CHECKPOINT="${SAM3D_CHECKPOINT:-}"
SAM3D_MHR_MODEL="${SAM3D_MHR_MODEL:-}"
SAM2_CHECKPOINTS_DIR="${SAM2_CHECKPOINTS_DIR:-}"
GLTFPACK_FILE="${GLTFPACK_FILE:-}"

note "Setting MinIO alias..."
run mc "${MC_EXTRA_ARGS[@]}" alias set "${MINIO_ALIAS}" "${MINIO_URL}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" >/dev/null

note "Ensuring bucket exists: ${MODELS_BUCKET}"
run mc "${MC_EXTRA_ARGS[@]}" mb -p "${MINIO_ALIAS}/${MODELS_BUCKET}" >/dev/null || true

upload_dir_contents() {
  local src_dir="$1"
  local dest="$2"
  dir_exists "${src_dir}"
  note "Uploading dir contents: ${src_dir} -> ${dest}"
  # Trailing slash copies *contents* of the directory, not the directory name.
  run mc "${MC_EXTRA_ARGS[@]}" cp --recursive "${src_dir%/}/" "${dest%/}/"
}

upload_file_as() {
  local src="$1"
  local dest="$2"
  file_exists "${src}"
  note "Uploading file: ${src} -> ${dest}"
  run mc "${MC_EXTRA_ARGS[@]}" cp "${src}" "${dest}"
}

if [[ -n "${SMPLX_DIR}" ]]; then
  upload_dir_contents "${SMPLX_DIR}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}smplx/"
else
  note "Skipping SMPL-X (SMPLX_DIR not set)"
fi

if [[ -n "${PIXIE_DATA_DIR}" ]]; then
  upload_dir_contents "${PIXIE_DATA_DIR}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}pixie/"
else
  note "Skipping PIXIE assets (PIXIE_DATA_DIR not set)"
fi

if [[ -n "${SAM3D_CHECKPOINT}" ]]; then
  upload_file_as "${SAM3D_CHECKPOINT}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}sam3d/model.ckpt"
else
  note "Skipping SAM3D checkpoint (SAM3D_CHECKPOINT not set)"
fi

if [[ -n "${SAM3D_MHR_MODEL}" ]]; then
  upload_file_as "${SAM3D_MHR_MODEL}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}sam3d/assets/mhr_model.pt"
else
  note "Skipping SAM3D MHR model (SAM3D_MHR_MODEL not set)"
fi

if [[ -n "${SAM2_CHECKPOINTS_DIR}" ]]; then
  upload_dir_contents "${SAM2_CHECKPOINTS_DIR}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}sam2/checkpoints/"
else
  note "Skipping SAM2 checkpoints (SAM2_CHECKPOINTS_DIR not set)"
fi

if [[ -n "${GLTFPACK_FILE}" ]]; then
  upload_file_as "${GLTFPACK_FILE}" "${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}tools/gltfpack"
else
  note "Skipping gltfpack (GLTFPACK_FILE not set)"
fi

note "Done."
note "Verify bucket contents:"
note "  mc ls --recursive ${MINIO_ALIAS}/${MODELS_BUCKET}/${remote_root}"
