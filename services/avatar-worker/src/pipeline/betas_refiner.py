"""
SMPL-X beta refinement from silhouette-derived targets.

This implements Option A: keep SMPL-X as the canonical body model for measurements
and garment fit, but refine betas so SMPL-Anthropometry measurements match targets
estimated from front+side silhouettes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BetaRefineConfig:
    max_nfev: int = 40
    weight_chest: float = 1.0
    weight_waist: float = 1.2
    weight_hip: float = 1.0
    weight_reg: float = 0.08


def _as_betas10(betas: np.ndarray) -> np.ndarray:
    b = np.asarray(betas, dtype=np.float32).reshape(-1)
    if b.size < 10:
        b = np.pad(b, (0, 10 - b.size))
    return b[:10]


def refine_betas_to_targets(
    *,
    measurement_extractor,
    initial_betas: np.ndarray,
    height_cm: float,
    targets: Dict[str, float],
    config: Optional[BetaRefineConfig] = None,
) -> np.ndarray:
    """
    Refine 10D betas to match target circumferences (cm) derived from silhouettes.

    measurement_extractor: instance of MeasurementExtractor (services/avatar-worker/src/pipeline/measurements.py)
    targets: expects keys chestCm/waistCm/hipCm
    """
    cfg = config or BetaRefineConfig()

    init = _as_betas10(initial_betas)

    # SciPy is already in requirements.txt
    from scipy.optimize import least_squares

    def predict(betas10: np.ndarray) -> Dict[str, float]:
        smplx_params = {"betas": betas10}
        m = measurement_extractor.extract_measurements(smplx_params)
        # normalize to requested height (scale everything by height ratio)
        pred_h = float(m.get("heightCm") or 0.0)
        if pred_h > 1e-3:
            s = float(height_cm) / pred_h
        else:
            s = 1.0
        return {
            "chestCm": float(m.get("chestCm") or 0.0) * s,
            "waistCm": float(m.get("waistCm") or 0.0) * s,
            "hipCm": float(m.get("hipCm") or 0.0) * s,
        }

    def residuals(x: np.ndarray) -> np.ndarray:
        pred = predict(_as_betas10(x))
        res = []
        if "chestCm" in targets:
            res.append((pred["chestCm"] - float(targets["chestCm"])) / 3.0 * cfg.weight_chest)
        if "waistCm" in targets:
            res.append((pred["waistCm"] - float(targets["waistCm"])) / 3.0 * cfg.weight_waist)
        if "hipCm" in targets:
            res.append((pred["hipCm"] - float(targets["hipCm"])) / 3.0 * cfg.weight_hip)

        # regularize betas towards 0 (and towards init a bit) to avoid implausible shapes
        res.extend(((x - init) * cfg.weight_reg).tolist())
        return np.asarray(res, dtype=np.float64)

    # keep betas bounded; typical SMPL-X betas are around [-3, 3]
    bounds = (-4.0 * np.ones(10), 4.0 * np.ones(10))
    result = least_squares(residuals, init, bounds=bounds, max_nfev=cfg.max_nfev)

    refined = _as_betas10(result.x)
    logger.info(
        "Beta refinement: success=%s cost=%.4f nfev=%s",
        bool(result.success),
        float(result.cost),
        int(result.nfev) if hasattr(result, "nfev") else None,
    )
    return refined

