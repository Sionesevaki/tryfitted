"""
Mask providers

Option A integration: use a strong external system (e.g. SAM 3D Body) to produce
foreground masks and keypoints, then refine SMPL-X betas using silhouette-derived
targets.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import types
import importlib.util
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MaskResult:
    provider: str
    mask_path: str
    keypoints_2d: Optional[list[list[float]]] = None
    bbox: Optional[list[float]] = None
    raw: Optional[Dict[str, Any]] = None


class MaskProvider:
    def generate(self, image_path: str, out_dir: str, prefix: str) -> MaskResult:
        raise NotImplementedError


class GrabCutMaskProvider(MaskProvider):
    """
    Simple, dependency-free fallback mask extractor.

    Works best with mostly clean backgrounds; intended as a fallback when SAM3DB is unavailable.
    """

    def generate(self, image_path: str, out_dir: str, prefix: str) -> MaskResult:
        os.makedirs(out_dir, exist_ok=True)

        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed to read image: {image_path}")

        height, width = img.shape[:2]
        rect = (
            int(width * 0.1),
            int(height * 0.05),
            int(width * 0.8),
            int(height * 0.9),
        )
        mask = np.zeros((height, width), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        mask_bin = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        out_path = os.path.join(out_dir, f"{prefix}_mask.png")
        cv2.imwrite(out_path, mask_bin)

        return MaskResult(provider="grabcut", mask_path=out_path, bbox=[float(v) for v in rect])


class Sam3DBodyMaskProvider(MaskProvider):
    """
    SAM 3D Body-backed mask + keypoint provider.

    This expects either:
    - `sam_3d_body` installed in the environment, OR
    - a clone of the repo available and pointed to by `SAM3DBODY_REPO_DIR`.
    """

    def __init__(
        self,
        repo_dir: str | None,
        checkpoint_path: str,
        mhr_path: str,
        detector_name: str = "vitdet",
        segmentor_name: str = "sam2",
        fov_name: str = "moge2",
        detector_path: str = "",
        segmentor_path: str = "",
        fov_path: str = "",
        use_mask: bool = True,
        bbox_thresh: float = 0.8,
    ) -> None:
        self.repo_dir = repo_dir
        self.checkpoint_path = checkpoint_path
        self.mhr_path = mhr_path
        self.detector_name = detector_name
        self.segmentor_name = segmentor_name
        self.fov_name = fov_name
        self.detector_path = detector_path
        self.segmentor_path = segmentor_path
        self.fov_path = fov_path
        self.use_mask = use_mask
        self.bbox_thresh = bbox_thresh

        self._estimator = None
        self._disabled_reason: str | None = None

    def _ensure_imports(self):
        # sam-3d-body depends on the tiny `braceexpand` package for data URL expansion.
        # Our integration doesn't require brace expansion, but the import is mandatory.
        # To keep local/dev environments frictionless, provide a minimal shim when missing.
        if "braceexpand" not in sys.modules:
            try:
                import braceexpand  # noqa: F401
            except Exception:
                shim = types.ModuleType("braceexpand")

                def _braceexpand(pattern: str):
                    # Minimal brace expansion shim:
                    # - If no braces are present, return the input as-is.
                    # - If braces are present, do a simple, single-level comma expansion:
                    #   "a{b,c}d" -> ["abd", "acd"]
                    # This is sufficient for sam-3d-body import-time usage in our pipeline.
                    if "{" not in pattern or "}" not in pattern:
                        return [pattern]
                    start = pattern.find("{")
                    end = pattern.find("}", start + 1)
                    if start == -1 or end == -1 or end < start:
                        return [pattern]
                    head = pattern[:start]
                    body = pattern[start + 1 : end]
                    tail = pattern[end + 1 :]
                    parts = [p for p in body.split(",") if p]
                    if not parts:
                        return [pattern]
                    return [f"{head}{p}{tail}" for p in parts]

                shim.braceexpand = _braceexpand  # type: ignore[attr-defined]
                sys.modules["braceexpand"] = shim
                logger.warning("braceexpand not installed; using minimal shim (install `braceexpand` for full support).")

        try:
            import sam_3d_body  # noqa: F401
            return
        except Exception:
            pass

        if not self.repo_dir:
            raise RuntimeError(
                "sam_3d_body is not importable and SAM3DBODY_REPO_DIR is not set. "
                "Install sam-3d-body or point SAM3DBODY_REPO_DIR at the cloned repo."
            )
        repo_dir = os.path.abspath(self.repo_dir)
        if not os.path.isdir(repo_dir):
            raise RuntimeError(f"SAM3DBODY_REPO_DIR does not exist: {repo_dir}")
        sys.path.insert(0, repo_dir)

    def _build_estimator(self):
        if self._estimator is not None:
            return
        if self._disabled_reason is not None:
            return

        required_modules = ["roma", "omegaconf", "yacs", "einops", "timm", "pytorch_lightning"]
        missing = [m for m in required_modules if importlib.util.find_spec(m) is None]
        if missing:
            self._disabled_reason = (
                "SAM3DB is enabled but required Python deps are missing: "
                f"{', '.join(missing)}. Install with `pip install -r services/avatar-worker/requirements.txt` "
                "(or `pip install " + " ".join(missing) + "`)."
            )
            return

        self._ensure_imports()

        import torch
        from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body

        # In practice, SAM3D Body relies on CUDA for inference.
        # When running on a CPU-only Torch build, fall back to GrabCut masks so the pipeline still works locally.
        if torch.version.cuda is None:
            self._disabled_reason = "Torch is not compiled with CUDA enabled."
            return
        if not torch.cuda.is_available():
            self._disabled_reason = "CUDA is not available (no GPU/driver)."
            return

        device = torch.device("cuda")

        model, model_cfg = load_sam_3d_body(self.checkpoint_path, device=device, mhr_path=self.mhr_path)

        human_detector = None
        human_segmentor = None
        fov_estimator = None

        try:
            from tools.build_detector import HumanDetector

            human_detector = HumanDetector(name=self.detector_name, device=device, path=self.detector_path)
        except Exception as e:
            logger.warning(f"SAM3DB: detector unavailable ({e}); using full image.")

        if self.use_mask:
            if device.type != "cuda":
                logger.warning("SAM3DB: SAM2 mask inference is disabled on CPU; using bbox-only + GrabCut fallback masks.")
            elif not self.segmentor_path:
                logger.warning("SAM3DB: SAM3DBODY_SEGMENTOR_PATH is empty; using bbox-only + GrabCut fallback masks.")
            else:
                try:
                    from tools.build_sam import HumanSegmentor

                    human_segmentor = HumanSegmentor(
                        name=self.segmentor_name, device=device, path=self.segmentor_path
                    )
                except Exception as e:
                    logger.warning(f"SAM3DB: segmentor unavailable ({e}); masks will be missing.")

        try:
            from tools.build_fov_estimator import FOVEstimator

            fov_estimator = FOVEstimator(name=self.fov_name, device=device, path=self.fov_path)
        except Exception as e:
            logger.warning(f"SAM3DB: fov estimator unavailable ({e}); using default FOV.")

        self._estimator = SAM3DBodyEstimator(
            sam_3d_body_model=model,
            model_cfg=model_cfg,
            human_detector=human_detector,
            human_segmentor=human_segmentor,
            fov_estimator=fov_estimator,
        )

    def _grabcut_from_bbox(self, image_path: str, bbox: list[float], out_path: str) -> None:
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed to read image: {image_path}")

        height, width = img.shape[:2]
        x0, y0, x1, y1 = [int(round(v)) for v in bbox]
        x0 = max(0, min(width - 1, x0))
        x1 = max(0, min(width, x1))
        y0 = max(0, min(height - 1, y0))
        y1 = max(0, min(height, y1))
        rect = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))

        mask = np.zeros((height, width), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        mask_bin = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        cv2.imwrite(out_path, mask_bin)

    def generate(self, image_path: str, out_dir: str, prefix: str) -> MaskResult:
        os.makedirs(out_dir, exist_ok=True)
        self._build_estimator()

        if self._estimator is None:
            # Best-effort fallback: still produce a silhouette so the downstream refinement can proceed.
            provider = GrabCutMaskProvider()
            result = provider.generate(image_path, out_dir, prefix)

            meta_path = os.path.join(out_dir, f"{prefix}_sam3db.json")
            meta = {
                "provider": "sam3d-body",
                "disabledReason": self._disabled_reason,
                "maskSource": "grabcut_fallback",
                "bbox": result.bbox,
                "pred_keypoints_2d": None,
            }
            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
            except Exception:
                pass

            return MaskResult(
                provider="grabcut",
                mask_path=result.mask_path,
                keypoints_2d=None,
                bbox=result.bbox,
                raw=meta,
            )

        try:
            outputs = self._estimator.process_one_image(  # type: ignore[union-attr]
                image_path,
                bbox_thr=self.bbox_thresh,
                use_mask=self.use_mask,
            )
        except Exception as e:
            if self.use_mask:
                logger.warning(f"SAM3DB mask run failed ({e}); retrying without SAM mask.")
                outputs = self._estimator.process_one_image(  # type: ignore[union-attr]
                    image_path,
                    bbox_thr=self.bbox_thresh,
                    use_mask=False,
                )
            else:
                raise
        if not outputs:
            raise RuntimeError("SAM3DB produced no detections for the image.")

        # pick largest bbox
        def bbox_area(o: Dict[str, Any]) -> float:
            b = o.get("bbox")
            if b is None:
                return 0.0
            return float(max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1])))

        best = max(outputs, key=bbox_area)

        mask = best.get("mask")
        out_path = os.path.join(out_dir, f"{prefix}_mask.png")
        if mask is None:
            # Minimal-assets fallback: approximate a person silhouette using bbox-initialized GrabCut.
            bbox = best.get("bbox")
            if bbox is None:
                raise RuntimeError("SAM3DB output has no bbox; cannot produce fallback mask.")
            self._grabcut_from_bbox(image_path, bbox=bbox, out_path=out_path)
        else:
            mask_u8 = (mask.astype(np.uint8) * 255) if mask.max() <= 1 else mask.astype(np.uint8)
            cv2.imwrite(out_path, mask_u8)

        meta_path = os.path.join(out_dir, f"{prefix}_sam3db.json")
        meta = {
            "provider": "sam3d-body",
            "bbox": best.get("bbox").tolist() if hasattr(best.get("bbox"), "tolist") else best.get("bbox"),
            "pred_keypoints_2d": best.get("pred_keypoints_2d").tolist()
            if hasattr(best.get("pred_keypoints_2d"), "tolist")
            else best.get("pred_keypoints_2d"),
            "maskSource": "sam3dbody" if best.get("mask") is not None else "grabcut_from_sam3dbody_bbox",
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return MaskResult(
            provider="sam3d-body",
            mask_path=out_path,
            keypoints_2d=meta.get("pred_keypoints_2d"),
            bbox=meta.get("bbox"),
            raw=meta,
        )
