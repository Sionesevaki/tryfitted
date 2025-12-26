"""
Avatar Worker - Main worker script for processing avatar generation jobs

This worker consumes jobs from Redis/BullMQ, processes photos using PIXIE,
extracts measurements, optimizes GLB output, and uploads results to MinIO.

NOTE: This is a placeholder implementation. To enable actual ML processing:
1. Clone PIXIE repository into src/pipeline/PIXIE
2. Clone SMPL-Anthropometry into src/pipeline/SMPL-Anthropometry
3. Download SMPL-X models to /app/models/smplx
4. Uncomment and implement actual PIXIE/SMPL-Anthropometry integration in:
   - pipeline/pixie_runner.py
   - pipeline/measurements.py
"""

import logging
import time
import os
import tempfile
import json
from typing import Dict, Any

from config import (
    REDIS_URL,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE,
    API_BASE_URL,
    SMPLX_MODEL_DIR,
    PIXIE_MODEL_DIR,
    REQUIRE_REAL_AVATAR,
    GLTFPACK_PATH,
    SAM3DBODY_ENABLED,
    SAM3DBODY_REPO_DIR,
    SAM3DBODY_CHECKPOINT_PATH,
    SAM3DBODY_MHR_PATH,
    SAM3DBODY_USE_MASK,
    SAM3DBODY_DETECTOR_PATH,
    SAM3DBODY_SEGMENTOR_PATH,
    SAM3DBODY_FOV_PATH,
    SILHOUETTE_REFINE_ENABLED,
    SILHOUETTE_TORSO_ERODE_PX,
)
from pipeline.pixie_runner import PIXIERunner
from pipeline.measurements import MeasurementExtractor
from pipeline.optimize_glb import GLBOptimizer
from pipeline.storage import StorageClient
from pipeline.appearance import estimate_skin_color_rgb, apply_skin_tone_to_glb
from pipeline.mask_provider import GrabCutMaskProvider, Sam3DBodyMaskProvider
from pipeline.silhouette_targets import estimate_targets_from_masks
from pipeline.betas_refiner import refine_betas_to_targets
from clients.api_client import APIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def to_jsonable(value: Any) -> Any:
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass

    try:
        import torch

        if isinstance(value, torch.Tensor):
            return value.detach().cpu().tolist()
    except Exception:
        pass

    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]

    return value


class AvatarWorker:
    """Avatar generation worker"""
    
    def __init__(self):
        """Initialize worker with all necessary clients"""
        logger.info("Initializing Avatar Worker...")
        
        self.storage = StorageClient(
            MINIO_ENDPOINT,
            MINIO_ACCESS_KEY,
            MINIO_SECRET_KEY,
            MINIO_BUCKET,
            MINIO_SECURE
        )
        
        self.api_client = APIClient(API_BASE_URL)
        self.pixie = PIXIERunner(PIXIE_MODEL_DIR, SMPLX_MODEL_DIR)
        self.measurer = MeasurementExtractor(SMPLX_MODEL_DIR)
        self.optimizer = GLBOptimizer(gltfpack_path=GLTFPACK_PATH)

        self.mask_provider = None
        if SAM3DBODY_ENABLED:
            if not SAM3DBODY_CHECKPOINT_PATH or not SAM3DBODY_MHR_PATH:
                logger.warning(
                    "SAM3DBODY_ENABLED=true but SAM3DBODY_CHECKPOINT_PATH/SAM3DBODY_MHR_PATH are not set; "
                    "disabling SAM3D-based masks."
                )
            else:
                try:
                    self.mask_provider = Sam3DBodyMaskProvider(
                        repo_dir=SAM3DBODY_REPO_DIR,
                        checkpoint_path=SAM3DBODY_CHECKPOINT_PATH,
                        mhr_path=SAM3DBODY_MHR_PATH,
                        use_mask=SAM3DBODY_USE_MASK,
                        detector_path=SAM3DBODY_DETECTOR_PATH,
                        segmentor_path=SAM3DBODY_SEGMENTOR_PATH,
                        fov_path=SAM3DBODY_FOV_PATH,
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize SAM3DBodyMaskProvider: {e}")

        if self.mask_provider is None:
            self.mask_provider = GrabCutMaskProvider()
        
        logger.info("Avatar Worker initialized successfully")
    
    def process_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Process avatar generation job
        
        Args:
            job_data: Job data containing jobId, frontPhotoUrl, heightCm, etc.
            
        Returns:
            True if successful, False otherwise
        """
        job_id = job_data.get("jobId")
        front_photo_url = job_data.get("frontPhotoUrl")
        side_photo_url = job_data.get("sidePhotoUrl")
        height_cm = job_data.get("heightCm")

        if not job_id:
            logger.error(f"Job missing jobId: {job_data}")
            return False

        logger.info(f"Processing job {job_id}")
        
        try:
            # Update status to processing
            self.api_client.update_job_status(job_id, "processing", progress=10)
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                def download_upload_url(url: str | None, dest_path: str) -> bool:
                    if not url:
                        open(dest_path, "w").close()
                        return False

                    if "uploads/" not in url:
                        open(dest_path, "w").close()
                        return False

                    parts = url.split("uploads/")
                    object_name = f"uploads/{parts[1]}"
                    try:
                        self.storage.download_file(object_name, dest_path)
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to download {url}, using placeholder: {e}")
                        open(dest_path, "w").close()
                        return False

                # Step 1: Download photos
                logger.info("Step 1: Downloading photos...")
                front_photo_path = os.path.join(temp_dir, "photo_front.jpg")
                side_photo_path = os.path.join(temp_dir, "photo_side.jpg")
                front_ok = download_upload_url(front_photo_url, front_photo_path)
                side_ok = download_upload_url(side_photo_url, side_photo_path)

                skin_rgb = estimate_skin_color_rgb(front_photo_path) if front_ok else None

                self.api_client.update_job_status(job_id, "processing", progress=20)
                
                # Step 2: Process with PIXIE (front + optional side)
                logger.info("Step 2: Processing with PIXIE...")
                smplx_params = self.pixie.process_images(
                    front_photo_path,
                    side_photo_path if side_ok else None,
                    height_cm,
                )
                if REQUIRE_REAL_AVATAR and smplx_params.get("placeholder"):
                    raise RuntimeError(
                        "Avatar generation ran in placeholder mode (PIXIE/SMPL-X assets not loaded). "
                        "Install required PIXIE data + weights and SMPL-X models, or unset REQUIRE_REAL_AVATAR."
                    )

                # Optional silhouette refinement (Option A): use masks to refine betas for better fit accuracy.
                if SILHOUETTE_REFINE_ENABLED and front_ok and side_ok and not smplx_params.get("placeholder"):
                    try:
                        logger.info("Step 2b: Generating masks + silhouette targets for refinement...")
                        debug_dir = os.path.join(temp_dir, "fit_debug")
                        front_mask = self.mask_provider.generate(front_photo_path, debug_dir, "front")
                        side_mask = self.mask_provider.generate(side_photo_path, debug_dir, "side")

                        targets = estimate_targets_from_masks(
                            front_mask_path=front_mask.mask_path,
                            side_mask_path=side_mask.mask_path,
                            height_cm=float(height_cm),
                            front_keypoints_2d=front_mask.keypoints_2d,
                            side_keypoints_2d=side_mask.keypoints_2d,
                            torso_erode_px=SILHOUETTE_TORSO_ERODE_PX,
                            save_debug_dir=debug_dir,
                        )

                        # Upload debug artifacts (best-effort)
                        try:
                            self.storage.upload_file(front_mask.mask_path, f"avatars/{job_id}/mask_front.png", content_type="image/png")
                            self.storage.upload_file(side_mask.mask_path, f"avatars/{job_id}/mask_side.png", content_type="image/png")
                            self.storage.upload_file(os.path.join(debug_dir, "front_sam3db.json"), f"avatars/{job_id}/front_sam3db.json", content_type="application/json")
                            self.storage.upload_file(os.path.join(debug_dir, "side_sam3db.json"), f"avatars/{job_id}/side_sam3db.json", content_type="application/json")
                            self.storage.upload_file(os.path.join(debug_dir, "silhouette_targets.json"), f"avatars/{job_id}/silhouette_targets.json", content_type="application/json")
                        except Exception:
                            pass

                        refined = refine_betas_to_targets(
                            measurement_extractor=self.measurer,
                            initial_betas=smplx_params.get("betas", []),
                            height_cm=float(height_cm),
                            targets={"chestCm": targets.chest_cm, "waistCm": targets.waist_cm, "hipCm": targets.hip_cm},
                        )
                        smplx_params["betas"] = refined
                        smplx_params["sources"] = {**(smplx_params.get("sources") or {}), "silhouetteRefine": True}

                        meshes = self.pixie.build_meshes_from_betas(refined, float(height_cm))
                        smplx_params.update(meshes)

                    except Exception as e:
                        logger.warning(f"Silhouette refinement skipped/failed: {e}")

                self.api_client.update_job_status(job_id, "processing", progress=40)
                
                # Step 3: Extract measurements
                logger.info("Step 3: Extracting measurements...")
                measurements = self.measurer.extract_measurements(smplx_params)
                quality_report = self.measurer.generate_quality_report(
                    measurements,
                    smplx_params.get("confidence", 0.0),
                    placeholder=bool(smplx_params.get("placeholder") or self.measurer.measurer is None)
                )
                
                self.api_client.update_job_status(job_id, "processing", progress=60)
                
                # Step 4: Export mesh
                logger.info("Step 4: Exporting mesh...")
                glb_path = os.path.join(temp_dir, "avatar.glb")
                self.pixie.export_mesh(smplx_params, glb_path)
                
                self.api_client.update_job_status(job_id, "processing", progress=70)
                
                # Step 5: Optimize GLB
                logger.info("Step 5: Optimizing GLB...")
                optimized_path = os.path.join(temp_dir, "avatar_optimized.glb")
                final_glb_path = self.optimizer.optimize(glb_path, optimized_path)

                if skin_rgb is not None:
                    apply_skin_tone_to_glb(final_glb_path, skin_rgb)
                
                self.api_client.update_job_status(job_id, "processing", progress=85)
                
                # Step 6: Upload to MinIO
                logger.info("Step 6: Uploading to MinIO...")
                object_name = f"avatars/{job_id}/avatar.glb"
                self.storage.upload_file(final_glb_path, object_name)
                glb_url = self.storage.get_public_url(object_name)

                measurements_path = os.path.join(temp_dir, "measurements.json")
                quality_report_path = os.path.join(temp_dir, "quality_report.json")
                appearance_path = os.path.join(temp_dir, "appearance.json")
                with open(measurements_path, "w", encoding="utf-8") as f:
                    json.dump(to_jsonable(measurements), f, indent=2)
                with open(quality_report_path, "w", encoding="utf-8") as f:
                    json.dump(to_jsonable(quality_report), f, indent=2)
                with open(appearance_path, "w", encoding="utf-8") as f:
                    appearance = {"sources": to_jsonable(smplx_params.get("sources"))}
                    if skin_rgb is not None:
                        r, g, b = skin_rgb
                        appearance["skinColor"] = {"rgb": [int(r), int(g), int(b)], "hex": f"#{r:02x}{g:02x}{b:02x}"}
                    json.dump(to_jsonable(appearance), f, indent=2)

                self.storage.upload_file(measurements_path, f"avatars/{job_id}/measurements.json", content_type="application/json")
                self.storage.upload_file(quality_report_path, f"avatars/{job_id}/quality_report.json", content_type="application/json")
                self.storage.upload_file(appearance_path, f"avatars/{job_id}/appearance.json", content_type="application/json")
                
                self.api_client.update_job_status(job_id, "processing", progress=95)
                
                # Step 7: Complete job
                logger.info("Step 7: Completing job...")
                # TODO: Get user_id from job data
                user_id = "default-user"
                result = {
                    "userId": user_id,
                    "glbUrl": glb_url,
                    "measurements": to_jsonable(measurements),
                    "qualityReport": to_jsonable(quality_report),
                }
                self.api_client.update_job_status(job_id, "completed", progress=100, result=result)
                
                logger.info(f"Job {job_id} completed successfully!")
                return True
                
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            self.api_client.update_job_status(job_id, "failed", error=str(e))
            return False


def main():
    """Main worker loop"""
    logger.info("Starting Avatar Worker...")
    
    worker = AvatarWorker()
    
    # Import Redis client
    from clients.redis_client import RedisClient
    
    try:
        # Connect to Redis
        redis_client = RedisClient(REDIS_URL)
        
        # Define job handler
        def handle_job(job_data: Dict[str, Any]) -> bool:
            """Handle avatar_build job"""
            return worker.process_job(job_data)
        
        # Start consuming jobs
        logger.info("Worker ready and listening for jobs...")
        redis_client.consume_jobs("avatar_build", handle_job)
        
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
