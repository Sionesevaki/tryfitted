#!/usr/bin/env python3
"""
Upload avatar-worker model assets into a private MinIO bucket (no `mc` required).

Requires Python 3.9+ and the `minio` package:
  python -m pip install minio

Env vars (required):
  MINIO_URL            e.g. https://minioapi.trifitted.com   (S3 API URL, not console)
  MINIO_ACCESS_KEY
  MINIO_SECRET_KEY

Env vars (optional):
  MODELS_BUCKET        default: trifitted-models
  MODELS_PREFIX        default: (empty)
  DRY_RUN              true/false
  MINIO_INSECURE       true/false   (disable TLS cert verification; use only for debugging)

Optional upload sources (set what you have):
  SMPLX_DIR
  PIXIE_DATA_DIR
  SAM3D_CHECKPOINT
  SAM3D_MHR_MODEL
  SAM2_CHECKPOINTS_DIR
  GLTFPACK_FILE        (Linux gltfpack binary)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _need(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"ERROR: Missing required env var: {name}")
    return value


def _note(message: str) -> None:
    print(f"[upload-models] {message}", file=sys.stderr)


def _resolve_repo_relative(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / path).resolve()


def _ensure_minio_imported():
    try:
        from minio import Minio  # noqa: F401
    except Exception:
        raise SystemExit(
            "ERROR: Python package 'minio' is not installed.\n\n"
            "Install it with:\n"
            "  python -m pip install minio\n"
        )


def _make_minio_client(minio_url: str, access_key: str, secret_key: str, insecure: bool):
    _ensure_minio_imported()
    from minio import Minio

    parsed = urlparse(minio_url)
    if parsed.scheme in {"http", "https"}:
        endpoint = parsed.netloc
        secure = parsed.scheme == "https"
    else:
        endpoint = minio_url
        secure = True

    http_client = None
    if insecure and secure:
        try:
            import urllib3

            http_client = urllib3.PoolManager(cert_reqs="CERT_NONE")
        except Exception as exc:
            raise SystemExit(
                "ERROR: MINIO_INSECURE=true requires urllib3.\n"
                "Try: python -m pip install urllib3\n"
                f"Details: {exc}"
            )

    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure, http_client=http_client)


def _ensure_bucket(client, bucket: str, dry_run: bool) -> None:
    if dry_run:
        _note(f"DRY_RUN: ensure bucket exists: {bucket}")
        return
    if client.bucket_exists(bucket):
        return
    client.make_bucket(bucket)


def _upload_file(client, bucket: str, object_name: str, file_path: Path, dry_run: bool) -> None:
    if dry_run:
        _note(f"DRY_RUN: put {file_path} -> s3://{bucket}/{object_name}")
        return
    client.fput_object(bucket, object_name, str(file_path))


def _upload_dir_contents(client, bucket: str, prefix: str, source_dir: Path, dry_run: bool) -> None:
    if not source_dir.is_dir():
        raise SystemExit(f"ERROR: Directory not found: {source_dir}")

    base = source_dir.resolve()
    for file_path in base.rglob("*"):
        if file_path.is_dir():
            continue
        rel = file_path.relative_to(base).as_posix()
        object_name = f"{prefix}{rel}"
        _upload_file(client, bucket, object_name, file_path, dry_run=dry_run)


def main() -> int:
    minio_url = _need("MINIO_URL")
    access_key = _need("MINIO_ACCESS_KEY")
    secret_key = _need("MINIO_SECRET_KEY")

    bucket = os.getenv("MODELS_BUCKET", "trifitted-models")
    models_prefix = os.getenv("MODELS_PREFIX", "")
    remote_root = models_prefix.strip("/").strip()
    remote_root = f"{remote_root}/" if remote_root else ""

    dry_run = _truthy(os.getenv("DRY_RUN"))
    insecure = _truthy(os.getenv("MINIO_INSECURE"))

    _note("Config:")
    _note(f"  MINIO_URL={minio_url}")
    _note(f"  MODELS_BUCKET={bucket}")
    _note(f"  MODELS_PREFIX={models_prefix or '<empty>'}")
    _note(f"  DRY_RUN={dry_run}")
    _note(f"  MINIO_INSECURE={insecure}")

    client = _make_minio_client(minio_url, access_key, secret_key, insecure=insecure)
    _ensure_bucket(client, bucket, dry_run=dry_run)

    # Sources (optional)
    smplx_dir = os.getenv("SMPLX_DIR", "")
    pixie_data_dir = os.getenv("PIXIE_DATA_DIR", "")
    sam3d_checkpoint = os.getenv("SAM3D_CHECKPOINT", "")
    sam3d_mhr = os.getenv("SAM3D_MHR_MODEL", "")
    sam2_checkpoints_dir = os.getenv("SAM2_CHECKPOINTS_DIR", "")
    gltfpack_file = os.getenv("GLTFPACK_FILE", "")

    if smplx_dir:
        src = _resolve_repo_relative(smplx_dir)
        _note(f"Uploading SMPL-X from {src} ...")
        _upload_dir_contents(client, bucket, f"{remote_root}smplx/", src, dry_run=dry_run)
    else:
        _note("Skipping SMPL-X (SMPLX_DIR not set)")

    if pixie_data_dir:
        src = _resolve_repo_relative(pixie_data_dir)
        _note(f"Uploading PIXIE assets from {src} ...")
        _upload_dir_contents(client, bucket, f"{remote_root}pixie/", src, dry_run=dry_run)
    else:
        _note("Skipping PIXIE assets (PIXIE_DATA_DIR not set)")

    if sam3d_checkpoint:
        src = _resolve_repo_relative(sam3d_checkpoint)
        if not src.is_file():
            raise SystemExit(f"ERROR: File not found: {src}")
        _note(f"Uploading SAM3D checkpoint from {src} ...")
        _upload_file(client, bucket, f"{remote_root}sam3d/model.ckpt", src, dry_run=dry_run)
    else:
        _note("Skipping SAM3D checkpoint (SAM3D_CHECKPOINT not set)")

    if sam3d_mhr:
        src = _resolve_repo_relative(sam3d_mhr)
        if not src.is_file():
            raise SystemExit(f"ERROR: File not found: {src}")
        _note(f"Uploading SAM3D MHR model from {src} ...")
        _upload_file(client, bucket, f"{remote_root}sam3d/assets/mhr_model.pt", src, dry_run=dry_run)
    else:
        _note("Skipping SAM3D MHR model (SAM3D_MHR_MODEL not set)")

    if sam2_checkpoints_dir:
        src = _resolve_repo_relative(sam2_checkpoints_dir)
        _note(f"Uploading SAM2 checkpoints from {src} ...")
        _upload_dir_contents(client, bucket, f"{remote_root}sam2/checkpoints/", src, dry_run=dry_run)
    else:
        _note("Skipping SAM2 checkpoints (SAM2_CHECKPOINTS_DIR not set)")

    if gltfpack_file:
        src = _resolve_repo_relative(gltfpack_file)
        if not src.is_file():
            raise SystemExit(f"ERROR: File not found: {src}")
        _note(f"Uploading gltfpack from {src} ...")
        _upload_file(client, bucket, f"{remote_root}tools/gltfpack", src, dry_run=dry_run)
    else:
        _note("Skipping gltfpack (GLTFPACK_FILE not set)")

    _note("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
