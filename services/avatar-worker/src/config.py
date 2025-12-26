import os
from dotenv import load_dotenv

load_dotenv()

_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_SMPLX_DIR = os.path.join(_SERVICE_ROOT, "models", "smplx")
_DEFAULT_PIXIE_DIR = os.path.join(_SERVICE_ROOT, "src", "pipeline", "PIXIE")

def _normalize_windows_dotenv_path(value: str | None) -> str | None:
    """
    python-dotenv decodes escape sequences inside quoted values (e.g. "\\t" -> tab).
    This is a common footgun for Windows paths like "C:\\Users\\me\\tools\\gltfpack.exe".
    If we see control characters, convert them back to their escaped form so the path works.
    """
    if value is None:
        return None

    if os.name != "nt":
        return value

    replacements = {
        "\t": r"\t",
        "\n": r"\n",
        "\r": r"\r",
        "\f": r"\f",
        "\v": r"\v",
        "\b": r"\b",
        "\a": r"\a",
    }

    if not any(ch in value for ch in replacements):
        return value

    return "".join(replacements.get(ch, ch) for ch in value)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "tryfitted")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3001")

# Model paths
SMPLX_MODEL_DIR = os.getenv("SMPLX_MODEL_DIR", _DEFAULT_SMPLX_DIR if os.path.isdir(_DEFAULT_SMPLX_DIR) else "/app/models/smplx")
PIXIE_MODEL_DIR = os.getenv("PIXIE_MODEL_DIR", _DEFAULT_PIXIE_DIR if os.path.isdir(_DEFAULT_PIXIE_DIR) else "/app/models/pixie")

# Processing configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
PROCESSING_TIMEOUT = int(os.getenv("PROCESSING_TIMEOUT", "300"))  # 5 minutes
REQUIRE_REAL_AVATAR = os.getenv("REQUIRE_REAL_AVATAR", "false").lower() == "true"
GLTFPACK_PATH = _normalize_windows_dotenv_path(os.getenv("GLTFPACK_PATH", "gltfpack")) or "gltfpack"

# Optional fit-accuracy refinement (Option A: masks + silhouette targets -> refine betas)
SAM3DBODY_ENABLED = os.getenv("SAM3DBODY_ENABLED", "false").lower() == "true"
SAM3DBODY_REPO_DIR = os.getenv("SAM3DBODY_REPO_DIR", "").strip() or None
SAM3DBODY_CHECKPOINT_PATH = os.getenv("SAM3DBODY_CHECKPOINT_PATH", "").strip()
SAM3DBODY_MHR_PATH = os.getenv("SAM3DBODY_MHR_PATH", "").strip()
SAM3DBODY_USE_MASK = os.getenv("SAM3DBODY_USE_MASK", "true").lower() == "true"
SAM3DBODY_DETECTOR_PATH = os.getenv("SAM3DBODY_DETECTOR_PATH", "").strip()
SAM3DBODY_SEGMENTOR_PATH = os.getenv("SAM3DBODY_SEGMENTOR_PATH", "").strip()
SAM3DBODY_FOV_PATH = os.getenv("SAM3DBODY_FOV_PATH", "").strip()
SILHOUETTE_REFINE_ENABLED = os.getenv("SILHOUETTE_REFINE_ENABLED", "true").lower() == "true"
SILHOUETTE_TORSO_ERODE_PX = int(os.getenv("SILHOUETTE_TORSO_ERODE_PX", "8"))
