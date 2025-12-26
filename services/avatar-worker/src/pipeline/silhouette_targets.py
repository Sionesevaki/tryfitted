"""
Silhouette-derived measurement targets.

Given front + side person masks and (optional) 2D keypoints, estimate key
cross-section circumferences (chest/waist/hip) in centimeters.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


MHR70 = {
    "left_shoulder": 5,
    "right_shoulder": 6,
    "left_hip": 9,
    "right_hip": 10,
    "neck": 69,
}


@dataclass
class SilhouetteTargets:
    height_px: int
    px_to_cm: float
    chest_cm: float
    waist_cm: float
    hip_cm: float
    debug: dict

    def to_dict(self) -> dict:
        return {
            "heightPx": int(self.height_px),
            "pxToCm": float(self.px_to_cm),
            "chestCm": float(self.chest_cm),
            "waistCm": float(self.waist_cm),
            "hipCm": float(self.hip_cm),
            "debug": self.debug,
        }


def _read_mask(mask_path: str) -> np.ndarray:
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise RuntimeError(f"Failed to read mask: {mask_path}")
    mask = (mask > 0).astype(np.uint8)
    return mask


def _preprocess_mask(mask: np.ndarray, erode_px: int) -> np.ndarray:
    mask_u8 = (mask * 255).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel, iterations=1)

    if erode_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px * 2 + 1, erode_px * 2 + 1))
        mask_u8 = cv2.erode(mask_u8, k, iterations=1)
        mask_u8 = cv2.dilate(mask_u8, k, iterations=1)

    return (mask_u8 > 0).astype(np.uint8)


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if ys.size == 0:
        raise RuntimeError("Mask is empty")
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    return x0, y0, x1, y1


def _width_at_y(mask: np.ndarray, y: int, center_x: int) -> int:
    y = int(np.clip(y, 0, mask.shape[0] - 1))
    row = mask[y, :]
    xs = np.where(row > 0)[0]
    if xs.size == 0:
        return 0

    # Choose contiguous segment closest to the center line (reduces arm influence when separable).
    splits = np.where(np.diff(xs) > 1)[0]
    segments = []
    start = 0
    for s in splits:
        segments.append(xs[start : s + 1])
        start = s + 1
    segments.append(xs[start:])

    best_seg = min(segments, key=lambda seg: abs(int(np.median(seg)) - center_x))
    return int(best_seg[-1] - best_seg[0] + 1)


def _ellipse_circumference(a_cm: float, b_cm: float) -> float:
    # Ramanujan approximation
    import math

    a = max(0.1, float(a_cm))
    b = max(0.1, float(b_cm))
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


def _infer_torso_ys_from_keypoints(keypoints_2d: Optional[list[list[float]]]) -> Optional[dict]:
    if not keypoints_2d:
        return None
    try:
        pts = np.asarray(keypoints_2d, dtype=np.float32)
        ls, rs = pts[MHR70["left_shoulder"]], pts[MHR70["right_shoulder"]]
        lh, rh = pts[MHR70["left_hip"]], pts[MHR70["right_hip"]]
        shoulders_y = float((ls[1] + rs[1]) / 2)
        hips_y = float((lh[1] + rh[1]) / 2)
        if hips_y <= shoulders_y:
            return None
        chest_y = shoulders_y + 0.35 * (hips_y - shoulders_y)
        waist_y = shoulders_y + 0.65 * (hips_y - shoulders_y)
        hip_y = hips_y
        return {"shouldersY": shoulders_y, "hipsY": hips_y, "chestY": chest_y, "waistY": waist_y, "hipY": hip_y}
    except Exception:
        return None


def estimate_targets_from_masks(
    front_mask_path: str,
    side_mask_path: str,
    height_cm: float,
    front_keypoints_2d: Optional[list[list[float]]] = None,
    side_keypoints_2d: Optional[list[list[float]]] = None,
    torso_erode_px: int = 8,
    save_debug_dir: Optional[str] = None,
) -> SilhouetteTargets:
    front = _preprocess_mask(_read_mask(front_mask_path), torso_erode_px)
    side = _preprocess_mask(_read_mask(side_mask_path), torso_erode_px)

    x0, y0, x1, y1 = _bbox_from_mask(front)
    height_px = max(1, y1 - y0 + 1)
    px_to_cm = float(height_cm) / float(height_px)

    center_x_front = int((x0 + x1) / 2)
    xs, ys = np.where(side > 0)
    center_x_side = int(np.median(xs)) if xs.size else int(side.shape[1] / 2)

    y_info_front = _infer_torso_ys_from_keypoints(front_keypoints_2d)
    y_info_side = _infer_torso_ys_from_keypoints(side_keypoints_2d)
    y_info = y_info_front or y_info_side

    if y_info:
        chest_y = int(y_info["chestY"])
        waist_y = int(y_info["waistY"])
        hip_y = int(y_info["hipY"])
    else:
        # fallback: ratios within mask bbox
        chest_y = int(y0 + 0.35 * height_px)
        waist_y = int(y0 + 0.55 * height_px)
        hip_y = int(y0 + 0.65 * height_px)
        y_info = {"chestY": chest_y, "waistY": waist_y, "hipY": hip_y, "fallback": True}

    fw_chest = _width_at_y(front, chest_y, center_x_front)
    fw_waist = _width_at_y(front, waist_y, center_x_front)
    fw_hip = _width_at_y(front, hip_y, center_x_front)

    sw_chest = _width_at_y(side, chest_y, center_x_side)
    sw_waist = _width_at_y(side, waist_y, center_x_side)
    sw_hip = _width_at_y(side, hip_y, center_x_side)

    def w_to_cm(w_px: int) -> float:
        return float(w_px) * px_to_cm

    # ellipse radii from widths
    chest_cm = _ellipse_circumference(w_to_cm(fw_chest) / 2.0, w_to_cm(sw_chest) / 2.0)
    waist_cm = _ellipse_circumference(w_to_cm(fw_waist) / 2.0, w_to_cm(sw_waist) / 2.0)
    hip_cm = _ellipse_circumference(w_to_cm(fw_hip) / 2.0, w_to_cm(sw_hip) / 2.0)

    debug = {
        "frontMask": os.path.basename(front_mask_path),
        "sideMask": os.path.basename(side_mask_path),
        "torsoErodePx": torso_erode_px,
        "yInfo": y_info,
        "frontWidthsPx": {"chest": fw_chest, "waist": fw_waist, "hip": fw_hip},
        "sideWidthsPx": {"chest": sw_chest, "waist": sw_waist, "hip": sw_hip},
    }

    if save_debug_dir:
        os.makedirs(save_debug_dir, exist_ok=True)
        with open(os.path.join(save_debug_dir, "silhouette_targets.json"), "w", encoding="utf-8") as f:
            json.dump(debug, f, indent=2)

    return SilhouetteTargets(
        height_px=height_px,
        px_to_cm=px_to_cm,
        chest_cm=chest_cm,
        waist_cm=waist_cm,
        hip_cm=hip_cm,
        debug=debug,
    )

