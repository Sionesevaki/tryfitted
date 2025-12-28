"""
Model sync utility for deployment.

Goal: avoid manual SCP/rsync into RunPod volumes.

If enabled, this script downloads required model assets from a private MinIO bucket
into `/app/models/*` (typically a mounted RunPod Network Volume).

It is intentionally conservative:
- only downloads files that are missing locally
- downloads by prefix (smplx/, pixie/, sam3d/, sam2/) so you can "mirror" folders into MinIO
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from minio import Minio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("model_sync")


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_prefix(client: Minio, bucket: str, remote_prefix: str, local_root: Path) -> int:
    downloaded = 0
    remote_prefix = remote_prefix.lstrip("/")
    if remote_prefix and not remote_prefix.endswith("/"):
        remote_prefix += "/"

    ensure_dir(local_root)

    logger.info(f"Syncing s3://{bucket}/{remote_prefix} -> {local_root}")
    for obj in client.list_objects(bucket, prefix=remote_prefix, recursive=True):
        if obj.is_dir:
            continue
        rel = obj.object_name[len(remote_prefix) :] if obj.object_name.startswith(remote_prefix) else obj.object_name
        dest = local_root / rel
        if dest.exists() and dest.is_file() and dest.stat().st_size == obj.size:
            continue
        ensure_dir(dest.parent)
        logger.info(f"Downloading {obj.object_name} ({obj.size} bytes) -> {dest}")
        client.fget_object(bucket, obj.object_name, str(dest))
        downloaded += 1
    return downloaded


def main() -> int:
    if not env_bool("MODEL_SYNC_ENABLED", "false"):
        logger.info("MODEL_SYNC_ENABLED is false; skipping model sync.")
        return 0

    endpoint = env_str("MODEL_SYNC_MINIO_ENDPOINT")
    access_key = env_str("MODEL_SYNC_MINIO_ACCESS_KEY")
    secret_key = env_str("MODEL_SYNC_MINIO_SECRET_KEY")
    bucket = env_str("MODEL_SYNC_MINIO_BUCKET", "tryfitted-models")
    secure = env_bool("MODEL_SYNC_MINIO_SECURE", "true")
    prefix_root = env_str("MODEL_SYNC_PREFIX", "").lstrip("/")

    if not endpoint or not access_key or not secret_key:
        logger.error("MODEL_SYNC_ENABLED=true but MODEL_SYNC_MINIO_* credentials are not fully set.")
        return 1

    # Comma-separated list of prefixes to sync from the bucket.
    # Each prefix syncs to /app/models/<name>.
    sources = [s.strip() for s in env_str("MODEL_SYNC_SOURCES", "smplx,pixie,sam3d,sam2").split(",") if s.strip()]

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    base = Path(env_str("MODEL_SYNC_LOCAL_ROOT", "/app/models"))
    total_downloaded = 0
    for name in sources:
        remote = f"{prefix_root}/{name}".strip("/")
        local = base / name
        total_downloaded += download_prefix(client, bucket=bucket, remote_prefix=remote, local_root=local)

    logger.info(f"Model sync complete; downloaded {total_downloaded} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
