"""
Appearance helpers

This module provides lightweight (dependency-minimal) helpers to improve perceived likeness:
- Estimate a reasonable skin tone from the input photo (heuristic skin mask)
- Apply that tone to the GLB material so the viewer matches the user better

These are intentionally simple and robust; for production you may replace this with a
segmentation model + proper color calibration.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np
from pygltflib import GLTF2, Material, PbrMetallicRoughness

logger = logging.getLogger(__name__)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def estimate_skin_color_rgb(image_path: str) -> Optional[Tuple[int, int, int]]:
    """
    Estimate skin tone from an image.

    Heuristic approach:
    - Use a central, upper region of the image (reduces background/clothing influence)
    - Apply a conservative skin mask in YCrCb + HSV
    - Take median color of masked pixels
    """
    img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return None

    height, width, _ = img_bgr.shape
    if height < 16 or width < 16:
        return None

    y0 = 0
    y1 = int(height * 0.65)
    x0 = int(width * 0.2)
    x1 = int(width * 0.8)
    roi = img_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return None

    ycrcb = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    mask_ycrcb = (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)

    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    mask_hsv = ((hue <= 25) | (hue >= 160)) & (sat >= 40) & (sat <= 230) & (val >= 60)

    mask = (mask_ycrcb & mask_hsv).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    pixels = roi[mask > 0]
    if pixels.shape[0] < 250:
        # Fallback: median over a small face-ish patch.
        py0 = int(height * 0.08)
        py1 = int(height * 0.28)
        px0 = int(width * 0.38)
        px1 = int(width * 0.62)
        patch = img_bgr[py0:py1, px0:px1]
        if patch.size == 0:
            return None
        pixels = patch.reshape(-1, 3)

    b, g, r = np.median(pixels, axis=0)
    rgb = (int(r), int(g), int(b))
    return rgb


def apply_skin_tone_to_glb(glb_path: str, rgb: Tuple[int, int, int]) -> bool:
    """
    Apply a baseColorFactor to all materials in a GLB.

    This is a safe "tint" even if textures exist (it multiplies the texture).
    """
    try:
        gltf = GLTF2().load(glb_path)
        r, g, b = rgb
        base = [r / 255.0, g / 255.0, b / 255.0, 1.0]

        if not gltf.materials:
            gltf.materials = [
                Material(
                    name="BodyMaterial",
                    pbrMetallicRoughness=PbrMetallicRoughness(
                        baseColorFactor=[1.0, 1.0, 1.0, 1.0],
                        metallicFactor=0.0,
                        roughnessFactor=1.0,
                    ),
                )
            ]

            if gltf.meshes:
                for mesh in gltf.meshes:
                    if not mesh.primitives:
                        continue
                    for prim in mesh.primitives:
                        if prim.material is None:
                            prim.material = 0

        for material in gltf.materials:
            if material.pbrMetallicRoughness is None:
                material.pbrMetallicRoughness = PbrMetallicRoughness()
            pbr = material.pbrMetallicRoughness
            if pbr.baseColorTexture is not None:
                continue
            pbr.baseColorFactor = base
            if pbr.metallicFactor is None:
                pbr.metallicFactor = 0.0
            if pbr.roughnessFactor is None:
                pbr.roughnessFactor = 1.0

        gltf.save(glb_path)
        logger.info("Applied skin tone %s to GLB materials", _rgb_to_hex(rgb))
        return True
    except Exception as e:
        logger.warning("Failed to apply skin tone to GLB (%s): %s", glb_path, e)
        return False
